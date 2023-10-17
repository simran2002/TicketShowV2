from flask import request, jsonify
from flask import current_app as app
import jwt
from functools import wraps


def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # jwt is passed in the request header
        if "access-token" in request.headers:
            token = request.headers["access-token"]
        # return 401 if token is not passed
        if not token:
            return {"msg": "Token is not provided"}, 401

        try:
            # decoding the payload to fetch the stored details
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        except:
            return {"msg": "Invalid token"}, 401
        return f(*args, **kwargs)

    return decorated
