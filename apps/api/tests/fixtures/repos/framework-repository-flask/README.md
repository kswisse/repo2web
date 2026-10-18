# Flask

A lightweight WSGI web application framework.

## Installation

```
pip install flask
```

## Usage

```python
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello, World!'
```
