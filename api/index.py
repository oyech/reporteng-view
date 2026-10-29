   # api/index.py
   from flask import Flask

   app = Flask(__name__)  # Variabel 'app' ini yang dicari otomatis oleh Vercel

   @app.route("/")
   def home():
       return "Hello from Flask on Vercel!"
