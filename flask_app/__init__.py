from flask import Flask

def create_app():
    app = Flask(__name__)

    # Configure the application (optional)
    app.config['SECRET_KEY'] = '1234567'

    # Import and register blueprints
    from .routes import main
    app.register_blueprint(main)

    return app