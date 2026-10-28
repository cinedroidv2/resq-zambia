from app import create_app, db
from app.models import incident

app = create_app()

with app.app_context():
    print("creating tables...")
    db.create_all()
    print("done creating tables")