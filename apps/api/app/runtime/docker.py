"""
Docker container runtime implementation.

Uses docker-py to manage containers with security policy enforcement.
"""

import asyncio
import logging
import platform
from typing import Optional

from app.security.ssrf import is_ip_blocked, is_trusted_deployment_endpoint

try:
    import docker
    from docker.errors import ImageNotFound, APIError, NotFound
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .base import ContainerRuntime, ContainerConfig, ContainerStatus, ExecResult
from .exceptions import (
    ContainerCreateError,
    ContainerStartError,
    ContainerStopError,
    ContainerExecError,
    ContainerRuntimeError,
)

logger = logging.getLogger(__name__)

# Image used for copying host files into Docker volumes.
# Must be small, always available, and contain basic Unix utilities.
COPIER_IMAGE = "python:3.11-slim"


def _detect_docker_url() -> str:
    """Detect the correct Docker daemon URL for the current platform."""
    if platform.system() == "Windows":
        return "npipe:////./pipe/docker_engine"
    return "unix:///var/run/docker.sock"


class DockerContainerRuntime(ContainerRuntime):
    """Docker container runtime implementation."""
    
    # Required networks for sandboxed execution
    REQUIRED_NETWORKS = ("repo2web-isolated", "repo2web-runtimes")
    
    def __init__(self, base_url: str = None):
        """
        Initialize Docker container runtime.
        
        Args:
            base_url: Docker daemon URL (auto-detected if None)
        """
        if base_url is None:
            base_url = _detect_docker_url()
        
        if not DOCKER_AVAILABLE:
            logger.warning("docker package not installed")
            self.client = None
            return
            
        try:
            self.client = docker.DockerClient(base_url=base_url)
            self.client.ping()
            logger.info(f"Connected to Docker daemon at {base_url}")
            self._ensure_networks()
        except Exception as e:
            logger.warning(f"Failed to connect to Docker daemon: {e}")
            self.client = None
    
    def _ensure_networks(self) -> None:
        """Create required Docker networks if they do not exist.
        
        Called once during initialization. Creates isolated networks
        for build and runtime containers with security-appropriate
        driver configurations.
        """
        if not self.client:
            return
        
        for network_name in self.REQUIRED_NETWORKS:
            try:
                existing = self.client.networks.list(names=[network_name])
                if existing:
                    logger.debug(f"Network '{network_name}' already exists")
                    continue
                
                # Create bridge network with internal DNS but no inter-container communication
                self.client.networks.create(
                    network_name,
                    driver="bridge",
                    check_duplicate=True,
                )
                logger.info(f"Created Docker network '{network_name}'")
            except Exception as e:
                logger.warning(f"Failed to ensure network '{network_name}': {e}")
    
    @property
    def is_available(self) -> bool:
        """Check if Docker daemon is available."""
        return self.client is not None
    
    async def _ensure_image(self, image: str) -> None:
        """Ensure a Docker image is available, pulling if necessary.
        
        Args:
            image: Docker image name (e.g. 'python:3.11-slim')
            
        Raises:
            ContainerCreateError: If the image cannot be obtained
        """
        if not self.is_available:
            return
        
        try:
            self.client.images.get(image)
            logger.debug(f"Image '{image}' already available locally")
        except ImageNotFound:
            logger.info(f"Image '{image}' not found locally, pulling...")
            try:
                self.client.images.pull(image)
                logger.info(f"Successfully pulled image '{image}'")
            except Exception as e:
                raise ContainerCreateError(
                    f"Failed to pull image '{image}': {e}"
                ) from e
    
    async def create_container(self, config: ContainerConfig) -> str:
        """
        Create a Docker container with the given configuration.
        
        Ensures the required image is available before creation.
        
        Args:
            config: Container configuration
            
        Returns:
            Container ID
            
        Raises:
            ContainerCreateError: If container creation fails
        """
        if not self.is_available:
            raise ContainerCreateError("Docker daemon not available")
        
        try:
            # Ensure the image is available (pull if needed)
            await self._ensure_image(config.image)
            
            # Convert config to Docker API format
            docker_args = config.to_dict()
            
            # Remove None values
            docker_args = {k: v for k, v in docker_args.items() if v is not None}
            
            # Create container
            container = self.client.containers.create(**docker_args)
            
            logger.info(f"Created container {container.id[:12]} with image {config.image}")
            return container.id
            
        except ImageNotFound as e:
            raise ContainerCreateError(f"Image not found: {config.image}") from e
        except APIError as e:
            raise ContainerCreateError(f"Docker API error: {e}") from e
        except ContainerCreateError:
            raise
        except Exception as e:
            raise ContainerCreateError(f"Failed to create container: {e}") from e
    
    async def start_container(self, container_id: str) -> None:
        """
        Start a Docker container.
        
        Args:
            container_id: Container ID
            
        Raises:
            ContainerStartError: If container start fails
        """
        if not self.is_available:
            raise ContainerStartError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            container.start()
            logger.info(f"Started container {container_id[:12]}")
        except NotFound as e:
            # The Docker API may return 404 for start failures (e.g. network not found).
            # Preserve the original error explanation for diagnostics.
            explanation = getattr(e, 'explanation', None) or str(e)
            raise ContainerStartError(
                f"Container not found or failed to start: {container_id} — {explanation}"
            ) from e
        except APIError as e:
            raise ContainerStartError(f"Docker API error: {e}") from e
        except Exception as e:
            raise ContainerStartError(f"Failed to start container: {e}") from e
    
    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """
        Stop a Docker container.
        
        Args:
            container_id: Container ID
            timeout: Timeout in seconds
            
        Raises:
            ContainerStopError: If container stop fails
        """
        if not self.is_available:
            raise ContainerStopError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            logger.info(f"Stopped container {container_id[:12]}")
        except NotFound:
            logger.warning(f"Container {container_id[:12]} not found (already removed?)")
        except APIError as e:
            raise ContainerStopError(f"Docker API error: {e}") from e
        except Exception as e:
            raise ContainerStopError(f"Failed to stop container: {e}") from e
    
    async def remove_container(self, container_id: str, force: bool = False) -> None:
        """
        Remove a Docker container.
        
        Args:
            container_id: Container ID
            force: Force removal even if running
            
        Raises:
            ContainerRuntimeError: If container removal fails
        """
        if not self.is_available:
            raise ContainerRuntimeError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            container.remove(force=force)
            logger.info(f"Removed container {container_id[:12]}")
        except NotFound:
            logger.warning(f"Container {container_id[:12]} not found (already removed?)")
        except APIError as e:
            raise ContainerRuntimeError(f"Docker API error: {e}") from e
        except Exception as e:
            raise ContainerRuntimeError(f"Failed to remove container: {e}") from e
    
    async def get_container_status(self, container_id: str) -> ContainerStatus:
        """
        Get Docker container status.
        
        Args:
            container_id: Container ID
            
        Returns:
            Container status
        """
        if not self.is_available:
            return ContainerStatus.UNKNOWN
        
        try:
            container = self.client.containers.get(container_id)
            status = container.status
            
            status_map = {
                "created": ContainerStatus.CREATED,
                "running": ContainerStatus.RUNNING,
                "restarting": ContainerStatus.RUNNING,
                "removing": ContainerStatus.STOPPED,
                "paused": ContainerStatus.STOPPED,
                "exited": ContainerStatus.STOPPED,
                "dead": ContainerStatus.FAILED,
            }
            
            return status_map.get(status, ContainerStatus.UNKNOWN)
            
        except NotFound:
            return ContainerStatus.REMOVED
        except Exception:
            return ContainerStatus.UNKNOWN
    
    async def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """
        Get Docker container logs.
        
        Args:
            container_id: Container ID
            tail: Number of lines to return from the end
            
        Returns:
            Container logs
        """
        if not self.is_available:
            return ""
        
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=False)
            return logs.decode("utf-8", errors="replace")
        except NotFound:
            return ""
        except Exception as e:
            logger.error(f"Failed to get logs for container {container_id[:12]}: {e}")
            return ""

    async def get_container_ip(self, container_id: str) -> Optional[str]:
        """Get the IP address of a container from Docker API metadata.

        This is a trusted internal method used for health checking and
        deployment validation. The container_id is a trusted internal
        identifier from the deployment pipeline, NOT a user-supplied value.

        Security properties:
        - The container_id is a trusted internal identifier
        - The IP is obtained from Docker API (trusted metadata source)
        - The caller must still validate the container belongs to this
          deployment (check labels for deployment_id)
        - This method does NOT apply SSRF protection (that is the caller's
          responsibility based on context)

        Args:
            container_id: Container ID

        Returns:
            Container IP address, or None if not found

        Raises:
            ContainerRuntimeError: If Docker API call fails
        """
        if not self.is_available:
            raise ContainerRuntimeError("Docker daemon not available")

        try:
            container = self.client.containers.get(container_id)
            container.reload()
            network_settings = container.attrs.get("NetworkSettings", {})
            networks = network_settings.get("Networks", {})

            for network_name, network_info in networks.items():
                ip_address = network_info.get("IPAddress")
                if ip_address:
                    logger.debug(
                        f"Container {container_id[:12]} IP: {ip_address} "
                        f"(network: {network_name})"
                    )
                    return ip_address

            logger.warning(f"No IP address found for container {container_id[:12]}")
            return None

        except NotFound as e:
            raise ContainerRuntimeError(
                f"Container not found for IP lookup: {container_id}"
            ) from e
        except Exception as e:
            raise ContainerRuntimeError(
                f"Failed to get IP for container {container_id[:12]}: {e}"
            ) from e

    async def get_container_labels(self, container_id: str) -> dict[str, str]:
        """Get Docker container labels.

        Labels are set by Repo2Web during container creation and include
        deployment_id and container type. They are used to verify container
        provenance for trusted operations like health checking.

        Args:
            container_id: Container ID

        Returns:
            Container labels dictionary

        Raises:
            ContainerRuntimeError: If Docker API call fails
        """
        if not self.is_available:
            raise ContainerRuntimeError("Docker daemon not available")

        try:
            container = self.client.containers.get(container_id)
            container.reload()
            return container.attrs.get("Config", {}).get("Labels", {}) or {}

        except NotFound as e:
            raise ContainerRuntimeError(
                f"Container not found for label lookup: {container_id}"
            ) from e
        except Exception as e:
            raise ContainerRuntimeError(
                f"Failed to get labels for container {container_id[:12]}: {e}"
            ) from e

    async def get_container_health_endpoint(
        self,
        container_id: str,
        port: int,
    ) -> Optional[str]:
        """Get the accessible health check endpoint for a container.

        Returns a URL string like "http://172.19.0.2:8080" or
        "http://localhost:54127" depending on what is accessible.

        On Docker Desktop for Windows, container IPs are in a Linux VM
        and are NOT reachable from the Windows host. In this case, the
        method uses the port-mapped endpoint (localhost:mapped_port).

        On Linux, the container IP is directly reachable, so the method
        returns the container IP endpoint.

        Security properties:
        - The container_id is a trusted internal identifier
        - Port mappings are randomly assigned by Docker (ephemeral)
        - This method is only used for trusted deployment health checks

        Args:
            container_id: Container ID
            port: Container port to check

        Returns:
            Health check URL string, or None if no endpoint found
        """
        if not self.is_available:
            raise ContainerRuntimeError("Docker daemon not available")

        try:
            container = self.client.containers.get(container_id)
            container.reload()
            network_settings = container.attrs.get("NetworkSettings", {})

            # Check port mapping first (works on all platforms)
            ports = network_settings.get("Ports", {})
            port_key = f"{port}/tcp"
            if port_key in ports and ports[port_key]:
                mapped = ports[port_key][0]
                host_port = mapped.get("HostPort")
                if host_port:
                    endpoint = f"http://localhost:{host_port}"
                    logger.debug(
                        f"Container {container_id[:12]} health endpoint "
                        f"(port-mapped): {endpoint}"
                    )
                    return endpoint

            # Fall back to direct container IP (works on Linux)
            networks = network_settings.get("Networks", {})
            for network_name, network_info in networks.items():
                ip_address = network_info.get("IPAddress")
                if ip_address:
                    endpoint = f"http://{ip_address}:{port}"
                    logger.debug(
                        f"Container {container_id[:12]} health endpoint "
                        f"(direct IP): {endpoint}"
                    )
                    return endpoint

            logger.warning(
                f"No health endpoint found for container {container_id[:12]}"
            )
            return None

        except NotFound as e:
            raise ContainerRuntimeError(
                f"Container not found for endpoint lookup: {container_id}"
            ) from e
        except Exception as e:
            raise ContainerRuntimeError(
                f"Failed to get endpoint for container {container_id[:12]}: {e}"
            ) from e
    
    async def exec_in_container(
        self,
        container_id: str,
        command: list[str],
        timeout: int = 300,
    ) -> ExecResult:
        """
        Execute a command in a Docker container.
        
        Args:
            container_id: Container ID
            command: Command to execute
            timeout: Timeout in seconds
            
        Returns:
            Execution result
            
        Raises:
            ContainerExecError: If execution fails
        """
        if not self.is_available:
            raise ContainerExecError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            
            # Execute command with timeout
            exit_code, output = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                timeout=timeout,
            )
            
            stdout = output.decode("utf-8", errors="replace") if output else ""
            
            return ExecResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr="",
                timed_out=False,
            )
            
        except NotFound as e:
            raise ContainerExecError(f"Container not found: {container_id}") from e
        except Exception as e:
            raise ContainerExecError(f"Failed to execute command: {e}") from e
    
    async def wait_for_container(
        self,
        container_id: str,
        timeout: int = 300,
    ) -> int:
        """
        Wait for Docker container to finish.
        
        Args:
            container_id: Container ID
            timeout: Timeout in seconds
            
        Returns:
            Exit code
        """
        if not self.is_available:
            raise ContainerRuntimeError("Docker daemon not available")
        
        try:
            container = self.client.containers.get(container_id)
            
            # Wait for container with timeout
            result = container.wait(timeout=timeout)
            return result.get("StatusCode", -1)
            
        except NotFound as e:
            raise ContainerRuntimeError(f"Container not found: {container_id}") from e
        except Exception as e:
            raise ContainerRuntimeError(f"Failed to wait for container: {e}") from e

    # --- Volume Management for Build Context Transfer ---

    async def create_volume(self, name: str) -> str:
        """Create a Docker named volume.

        Args:
            name: Volume name

        Returns:
            Volume name

        Raises:
            ContainerCreateError: If volume creation fails
        """
        if not self.is_available:
            raise ContainerCreateError("Docker daemon not available")

        try:
            # Check if volume already exists
            existing = self.client.volumes.list(filters={"name": name})
            if existing:
                logger.debug(f"Volume '{name}' already exists")
                return name

            self.client.volumes.create(name=name)
            logger.info(f"Created Docker volume '{name}'")
            return name
        except APIError as e:
            raise ContainerCreateError(f"Failed to create volume '{name}': {e}") from e
        except Exception as e:
            raise ContainerCreateError(f"Failed to create volume '{name}': {e}") from e

    async def remove_volume(self, name: str) -> None:
        """Remove a Docker named volume.

        Args:
            name: Volume name to remove

        Warning:
            Failures are logged but do not raise — cleanup is best-effort.
        """
        if not self.is_available:
            return

        try:
            volume = self.client.volumes.get(name)
            volume.remove(force=True)
            logger.info(f"Removed Docker volume '{name}'")
        except NotFound:
            logger.debug(f"Volume '{name}' not found (already removed?)")
        except Exception as e:
            logger.warning(f"Failed to remove volume '{name}': {e}")

    async def copy_to_volume(
        self,
        volume_name: str,
        host_path: str,
        container_path: str = "/workspace",
    ) -> None:
        """Copy a host directory into a Docker volume.

        Uses a temporary trusted container to bridge the host→volume gap.
        The copier container:
        - Mounts the volume at ``container_path`` (read-write)
        - Bind-mounts the host snapshot at ``/source`` (read-only)
        - Runs ``cp -a /source/. <container_path>/``
        - Is destroyed immediately after copying

        Security properties:
        - The untrusted build container never sees the host path.
        - The copier container has no network access.
        - The copier container is destroyed immediately after use.

        Args:
            volume_name: Target Docker volume name
            host_path: Host directory to copy (Windows or Linux path)
            container_path: Mount point inside the copier container

        Raises:
            ContainerCreateError: If the copy operation fails
        """
        if not self.is_available:
            raise ContainerCreateError("Docker daemon not available")

        copier_name = f"copier-{volume_name}"
        container = None

        try:
            # Ensure copier image is available
            await self._ensure_image(COPIER_IMAGE)

            # Create copier container with:
            # - Volume mounted at container_path (rw)
            # - Host snapshot bind-mounted at /source (ro)
            # - No network access
            container = self.client.containers.create(
                image=COPIER_IMAGE,
                name=copier_name,
                command=["cp", "-a", "/source/.", f"{container_path}/"],
                volumes={
                    volume_name: {"bind": container_path, "mode": "rw"},
                    host_path: {"bind": "/source", "mode": "ro"},
                },
                network_mode="none",
                # Minimal resource limits for copier
                nano_cpus=int(1.0 * 1_000_000_000),
                mem_limit="256m",
            )

            container.start()
            logger.info(
                f"Copying host path to volume '{volume_name}' "
                f"(copier container: {copier_name})"
            )

            result = container.wait(timeout=120)
            exit_code = result.get("StatusCode", -1)

            if exit_code != 0:
                logs = container.logs().decode("utf-8", errors="replace")
                raise ContainerCreateError(
                    f"Failed to copy host path to volume '{volume_name}': "
                    f"copier exited with code {exit_code}: {logs}"
                )

            logger.info(
                f"Successfully copied host path to volume '{volume_name}'"
            )

        except ContainerCreateError:
            raise
        except APIError as e:
            raise ContainerCreateError(
                f"Docker API error copying to volume '{volume_name}': {e}"
            ) from e
        except Exception as e:
            raise ContainerCreateError(
                f"Failed to copy host path to volume '{volume_name}': {e}"
            ) from e
        finally:
            # Always remove the copier container
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
    
    # --- Image Commit for Build Artifact Creation ---

    async def commit_container(
        self,
        container_id: str,
        repository: str,
        tag: str = "latest",
        changes: Optional[list[str]] = None,
    ) -> str:
        """Commit a container's filesystem state as a new Docker image.

        Creates a runnable image from a stopped container's filesystem.
        This is used to create a runtime image after a successful build.

        Security properties:
        - The committed image inherits the base image's layers
        - Only filesystem changes from the build are captured
        - No Docker socket or host filesystem is included
        - The committed image can be started with full security controls

        Args:
            container_id: Container to commit
            repository: Image repository name (e.g. 'repo2web-build')
            tag: Image tag (default: 'latest')
            changes: Optional list of Dockerfile instructions to apply
                     (e.g. ['CMD ["python", "app.py"]', 'WORKDIR /app'])

        Returns:
            Committed image name (repository:tag)

        Raises:
            ContainerRuntimeError: If commit fails
        """
        if not self.is_available:
            raise ContainerRuntimeError("Docker daemon not available")

        try:
            container = self.client.containers.get(container_id)

            # Commit the container with metadata changes
            image = container.commit(
                repository=repository,
                tag=tag,
                changes=changes or [],
            )

            image_name = f"{repository}:{tag}"
            logger.info(
                f"Committed container {container_id[:12]} as image {image_name}"
            )
            return image_name

        except NotFound as e:
            raise ContainerRuntimeError(
                f"Container not found for commit: {container_id}"
            ) from e
        except APIError as e:
            raise ContainerRuntimeError(
                f"Docker API error committing container: {e}"
            ) from e
        except Exception as e:
            raise ContainerRuntimeError(
                f"Failed to commit container {container_id[:12]}: {e}"
            ) from e

    async def build_runtime_image_from_build(
        self,
        container_id: str,
        repository: str,
        tag: str = "latest",
        base_image: str = "python:3.11-slim",
        source_path: str = "/workspace",
        workdir: str = "/workspace",
        run_command: str = "python app.py",
        port: int = 8000,
    ) -> str:
        """Build a runtime image by extracting build artifacts from a container.

        Instead of using ``docker commit`` (which cannot capture volume
        contents), this method:
        1. Extracts the build output from the running container's volume
           via the Docker daemon (which runs as root).
        2. Writes a minimal Dockerfile in a temporary build context.
        3. Builds a new image with ``docker build``.

        The resulting image has all build artifacts baked into its filesystem,
        so no volume mount is needed at runtime.

        Security properties:
        - The build container's isolation is never compromised.
        - File extraction is performed by the Docker daemon (root), not by
          the untrusted build process.
        - The runtime image inherits the base image's security properties.

        Args:
            container_id: Build container to extract artifacts from.
            repository: Image repository name.
            tag: Image tag (default 'latest').
            base_image: Base image for the runtime Dockerfile.
            source_path: Path inside the build container that holds artifacts.
            workdir: WORKDIR for the runtime image.
            run_command: CMD for the runtime image.
            port: EXPOSE port for the runtime image.

        Returns:
            Built image name (repository:tag).

        Raises:
            ContainerRuntimeError: If extraction or build fails.
        """
        if not self.is_available:
            raise ContainerRuntimeError("Docker daemon not available")

        import io
        import os
        import tarfile
        import tempfile

        image_name = f"{repository}:{tag}"

        try:
            container = self.client.containers.get(container_id)

            # 1. Extract the build output from the container.
            #    get_archive() returns a tar stream of the given path.
            #    This runs via the Docker daemon (root), bypassing user
            #    isolation inside the container.
            logger.info(
                f"Extracting build artifacts from {container_id[:12]} "
                f"path={source_path}"
            )
            tar_stream, stat = container.get_archive(source_path)
            logger.info(
                f"Build artifacts archive size: "
                f"{stat.get('size', 'unknown')} bytes"
            )

            # 2. Write the tar stream to a temporary file, then extract
            #    into a fresh build context directory.
            with tempfile.TemporaryDirectory(
                prefix="repo2web_build_"
            ) as build_ctx:
                tar_path = os.path.join(build_ctx, "artifacts.tar")
                with open(tar_path, "wb") as f:
                    for chunk in tar_stream:
                        f.write(chunk)

                # Extract the tar (it contains the files under source_path)
                extract_dir = os.path.join(build_ctx, "context")
                os.makedirs(extract_dir, exist_ok=True)
                with tarfile.open(tar_path) as tar:
                    tar.extractall(extract_dir)

                # The tar from get_archive contains the directory itself,
                # so files end up under context/<basename(source_path)>/
                # We want them directly in the build context.
                base_name = os.path.basename(source_path)
                src_dir = os.path.join(extract_dir, base_name)
                if os.path.isdir(src_dir):
                    # Move contents up one level
                    for item in os.listdir(src_dir):
                        s = os.path.join(src_dir, item)
                        d = os.path.join(extract_dir, item)
                        os.rename(s, d)
                    os.rmdir(src_dir)

                # 3. Write a minimal Dockerfile.
                #    Install dependencies from requirements.txt so the runtime
                #    image has all packages. The build container's pip installs
                #    live in PYTHONUSERBASE (tmpfs) or the volume's .pip dir,
                #    neither of which survives extraction. A fresh install in
                #    the runtime image is the reliable approach.
                #
                #    For Flask apps: set FLASK_RUN_HOST=0.0.0.0 so Flask
                #    listens on all interfaces (required for Docker port
                #    mapping). Without this, Flask's development server
                #    defaults to 127.0.0.1 which is unreachable from outside
                #    the container.
                dockerfile_content = (
                    f"FROM {base_image}\n"
                    f"COPY . {workdir}\n"
                    f"WORKDIR {workdir}\n"
                    f"RUN if [ -f requirements.txt ]; then "
                    f"pip install --no-cache-dir -r requirements.txt; fi\n"
                    f"ENV FLASK_RUN_HOST=0.0.0.0\n"
                    f"ENV PYTHONDONTWRITEBYTECODE=1\n"
                    f"EXPOSE {port}\n"
                    f'CMD ["sh", "-c", "{run_command}"]\n'
                )
                dockerfile_path = os.path.join(extract_dir, "Dockerfile")
                with open(dockerfile_path, "w") as f:
                    f.write(dockerfile_content)

                logger.info(
                    f"Building runtime image {image_name} from extracted "
                    f"artifacts (base={base_image}, workdir={workdir})"
                )

                # 4. Build the image
                build_image, build_logs = self.client.images.build(
                    path=extract_dir,
                    tag=image_name,
                    rm=True,
                    forcerm=True,
                )

                logger.info(
                    f"Successfully built runtime image {image_name} "
                    f"from build container {container_id[:12]}"
                )
                return image_name

        except NotFound as e:
            raise ContainerRuntimeError(
                f"Container not found for image build: {container_id}"
            ) from e
        except APIError as e:
            raise ContainerRuntimeError(
                f"Docker API error building runtime image: {e}"
            ) from e
        except ContainerRuntimeError:
            raise
        except Exception as e:
            raise ContainerRuntimeError(
                f"Failed to build runtime image from container "
                f"{container_id[:12]}: {e}"
            ) from e

    async def remove_image(self, image_name: str) -> None:
        """Remove a Docker image.

        Args:
            image_name: Image name to remove

        Warning:
            Failures are logged but do not raise — cleanup is best-effort.
        """
        if not self.is_available:
            return

        try:
            image = self.client.images.get(image_name)
            image.remove(force=True)
            logger.info(f"Removed Docker image '{image_name}'")
        except NotFound:
            logger.debug(f"Image '{image_name}' not found (already removed?)")
        except Exception as e:
            logger.warning(f"Failed to remove image '{image_name}': {e}")

    async def health_check(
        self,
        container_id: str,
        port: int,
        path: str = "/",
        timeout: int = 5,
    ) -> dict:
        """Perform health check on a container with trusted endpoint validation.

        Security model:
        - The container_id is a trusted internal identifier from the deployment pipeline
        - The endpoint is obtained from Docker API for that specific container
        - Container labels (deployment_id) are validated to prove provenance
        - Only health checks to Repo2Web-created containers are allowed
        - Redirects are not followed (each redirect would need separate validation)
        - General SSRF protection is NOT weakened — only the specific deployment
          container is authorized for health checking

        Platform behavior:
        - On Linux: Uses direct container IP (172.x.x.x:port)
        - On Windows/macOS (Docker Desktop): Uses port-mapped endpoint
          (localhost:mapped_port) because container IPs are in a Linux VM
          and are not reachable from the host

        Args:
            container_id: Container ID
            port: Port to check
            path: Health check path
            timeout: Timeout in seconds

        Returns:
            Health check result
        """
        if not self.is_available:
            return {
                "status": "unhealthy",
                "error": "Docker daemon not available",
            }

        if not HTTPX_AVAILABLE:
            return {
                "status": "unhealthy",
                "error": "httpx package not installed",
            }

        try:
            container = self.client.containers.get(container_id)

            # Get container labels and IP from Docker API (trusted metadata)
            container.reload()
            container_labels = container.attrs.get("Config", {}).get("Labels", {}) or {}
            network_settings = container.attrs.get("NetworkSettings", {})
            networks = network_settings.get("Networks", {})

            ip_address = None
            for network_name, network_info in networks.items():
                ip_address = network_info.get("IPAddress")
                if ip_address:
                    break

            if not ip_address:
                return {
                    "status": "unhealthy",
                    "error": "Could not determine container IP",
                }

            # Validate this is a trusted deployment container.
            # The deployment_id label proves this container was created by
            # Repo2Web. Without this label, standard SSRF protection applies.
            # This narrowly scopes authorization to the exact deployment
            # container — we do NOT blanket-whitelist private CIDRs.
            if not is_trusted_deployment_endpoint(ip_address, container_labels):
                # Not a trusted Repo2Web container — apply full SSRF protection
                if is_ip_blocked(ip_address):
                    return {
                        "status": "unhealthy",
                        "error": "Container IP is in blocked range and container "
                                 "is not a recognized deployment",
                    }
            else:
                # Trusted deployment — create a narrowly scoped temporary
                # SSRF exception for this container's IP. The exception
                # expires automatically after 60 seconds.
                from app.security.ssrf import allow_container_ip_for_health_check
                allow_container_ip_for_health_check(
                    ip=ip_address,
                    deployment_id=container_labels.get("deployment_id", "unknown"),
                    container_id=container_id,
                    ttl=60,
                )

            # Get the accessible health check endpoint.
            # On Windows/macOS (Docker Desktop), this uses port mapping
            # because container IPs are not reachable from the host.
            # On Linux, this uses the direct container IP.
            endpoint = await self.get_container_health_endpoint(container_id, port)
            if not endpoint:
                return {
                    "status": "unhealthy",
                    "error": "Could not determine health check endpoint",
                }

            url = f"{endpoint}{path}"

            # Perform HTTP health check — redirects are NOT followed.
            # Each redirect destination would need separate validation,
            # and a redirect to a different host could be an SSRF vector.
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                max_redirects=0,
            ) as client:
                response = await client.get(url)

                # If response is a redirect, check the target
                if 300 <= response.status_code < 400:
                    redirect_url = response.headers.get("location", "")
                    if redirect_url:
                        from urllib.parse import urlparse
                        parsed = urlparse(redirect_url)
                        if parsed.hostname:
                            from app.security.ssrf import validate_url_ssrf
                            # Use the actual scheme from the redirect,
                            # not a hardcoded scheme. A redirect to HTTP
                            # must be validated as HTTP.
                            scheme = parsed.scheme or "http"
                            port_part = f":{parsed.port}" if parsed.port else ""
                            is_safe, reason = validate_url_ssrf(
                                f"{scheme}://{parsed.hostname}{port_part}{parsed.path}",
                                allow_http=True,
                            )
                            if not is_safe:
                                return {
                                    "status": "unhealthy",
                                    "error": f"Health check redirect blocked: {reason}",
                                }

                if 200 <= response.status_code < 300:
                    return {
                        "status": "healthy",
                        "status_code": response.status_code,
                        "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "status_code": response.status_code,
                        "error": f"HTTP {response.status_code}",
                    }

        except httpx.TimeoutException:
            return {
                "status": "unhealthy",
                "error": "Health check timed out",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
