# FastAPI

FastAPI framework, high performance, easy to learn, fast to code, ready for production.

## Installation

```
pip install fastapi
```

## Usage

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
```
