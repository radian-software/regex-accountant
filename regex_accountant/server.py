import flask

app = flask.Flask(__name__)


@app.route("/")
def route_app():
    return "Hello world"
