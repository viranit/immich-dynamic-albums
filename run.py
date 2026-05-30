"""Application entry point."""
import os
from app import create_app, db

app = create_app(os.getenv('FLASK_ENV', 'default'))


@app.shell_context_processor
def make_shell_context():
    """Make database and models available in shell."""
    from app import models
    return {'db': db, 'models': models}


@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()
    print('Database initialized.')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
