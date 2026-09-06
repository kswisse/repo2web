"""Dependency Detector module.

Detects external service dependencies from package manifests and configuration.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional

from app.analyzer.types import ServiceDependency


# Service detection rules
SERVICE_RULES = [
    {
        "name": "postgresql",
        "dependencies": [
            "psycopg2",
            "psycopg2-binary",
            "asyncpg",
            "aiopg",
            "sqlalchemy",
            "django",
        ],
        "config_patterns": [
            r"postgresql://",
            r"postgres://",
            r"DATABASE_URL.*postgres",
        ],
        "evidence_prefix": "PostgreSQL",
    },
    {
        "name": "mysql",
        "dependencies": [
            "pymysql",
            "mysqlclient",
            "mysql-connector-python",
            "aiomysql",
            "sqlalchemy",
        ],
        "config_patterns": [
            r"mysql://",
            r"DATABASE_URL.*mysql",
        ],
        "evidence_prefix": "MySQL",
    },
    {
        "name": "sqlite",
        "dependencies": [
            "sqlite3",
            "aiosqlite",
        ],
        "config_patterns": [
            r"sqlite://",
            r"\.db$",
        ],
        "evidence_prefix": "SQLite",
    },
    {
        "name": "redis",
        "dependencies": [
            "redis",
            "aioredis",
            "fakeredis",
        ],
        "config_patterns": [
            r"redis://",
            r"REDIS_URL",
        ],
        "evidence_prefix": "Redis",
    },
    {
        "name": "mongodb",
        "dependencies": [
            "pymongo",
            "motor",
            "mongoose",
        ],
        "config_patterns": [
            r"mongodb://",
            r"mongo://",
            r"MONGO_URL",
            r"MONGODB_URI",
        ],
        "evidence_prefix": "MongoDB",
    },
    {
        "name": "elasticsearch",
        "dependencies": [
            "elasticsearch",
            "elasticsearch-py",
            "opensearch-py",
        ],
        "config_patterns": [
            r"elasticsearch://",
            r"ELASTICSEARCH_URL",
        ],
        "evidence_prefix": "Elasticsearch",
    },
    {
        "name": "rabbitmq",
        "dependencies": [
            "pika",
            "celery",
            "kombu",
        ],
        "config_patterns": [
            r"amqp://",
            r"RABBITMQ_URL",
        ],
        "evidence_prefix": "RabbitMQ",
    },
]


def detect_service_dependencies(
    key_files: dict[str, Optional[str]],
    manifest_dependencies: dict[str, str],
) -> list[ServiceDependency]:
    """Detect service dependencies from manifests and configuration.

    Args:
        key_files: Dictionary of key file contents.
        manifest_dependencies: Parsed dependencies from manifests.

    Returns:
        List of detected service dependencies.
    """
    services = {}

    # Check manifest dependencies
    for rule in SERVICE_RULES:
        for dep in rule["dependencies"]:
            if dep in manifest_dependencies:
                if rule["name"] not in services:
                    services[rule["name"]] = {
                        "name": rule["name"],
                        "required": True,
                        "evidence": [],
                    }
                services[rule["name"]]["evidence"].append(
                    f"Dependency '{dep}' found in manifest"
                )

    # Check configuration files
    config_files = [
        "docker-compose.yml",
        "docker-compose.yaml",
        "docker-compose.dev.yml",
        "docker-compose.prod.yml",
        ".env",
        ".env.example",
        ".env.sample",
        "config.py",
        "settings.py",
        "config.js",
        "config.ts",
    ]

    for config_file in config_files:
        content = key_files.get(config_file)
        if not content:
            continue

        for rule in SERVICE_RULES:
            for pattern in rule["config_patterns"]:
                if re.search(pattern, content):
                    if rule["name"] not in services:
                        services[rule["name"]] = {
                            "name": rule["name"],
                            "required": True,
                            "evidence": [],
                        }
                    services[rule["name"]]["evidence"].append(
                        f"Pattern '{pattern}' found in {config_file}"
                    )

    # Check for Docker Compose services
    docker_compose_services = _detect_docker_compose_services(key_files)
    for service_name, service_info in docker_compose_services.items():
        if service_name not in services:
            services[service_name] = {
                "name": service_name,
                "required": True,
                "evidence": [],
            }
        services[service_name]["evidence"].extend(service_info["evidence"])

    return [
        ServiceDependency(
            name=info["name"],
            required=info["required"],
            evidence=info["evidence"],
        )
        for info in services.values()
    ]


def _detect_docker_compose_services(key_files: dict[str, Optional[str]]) -> dict:
    """Detect services from docker-compose files.

    Args:
        key_files: Dictionary of key file contents.

    Returns:
        Dictionary of detected services.
    """
    services = {}

    compose_files = [
        "docker-compose.yml",
        "docker-compose.yaml",
        "docker-compose.dev.yml",
        "docker-compose.prod.yml",
    ]

    for compose_file in compose_files:
        content = key_files.get(compose_file)
        if not content:
            continue

        try:
            compose_data = json.loads(content) if content.strip().startswith("{") else None
        except json.JSONDecodeError:
            compose_data = None

        # Simple YAML-like parsing for common patterns
        if not compose_data:
            # Look for service definitions
            service_patterns = [
                (r"postgres:", "postgresql"),
                (r"mysql:", "mysql"),
                (r"redis:", "redis"),
                (r"mongo:", "mongodb"),
                (r"elasticsearch:", "elasticsearch"),
                (r"rabbitmq:", "rabbitmq"),
            ]

            for pattern, service_name in service_patterns:
                if re.search(pattern, content):
                    if service_name not in services:
                        services[service_name] = {
                            "name": service_name,
                            "required": True,
                            "evidence": [],
                        }
                    services[service_name]["evidence"].append(
                        f"Service '{service_name}' found in {compose_file}"
                    )

    return services
