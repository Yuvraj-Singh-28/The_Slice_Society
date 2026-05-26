import json
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, session, flash, redirect, url_for, Response
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'mysecretkey'


@app.route('/')
def index():
    return render_template('index.html')




# last line of code
if __name__ == '__main__':
    app.run(debug=True, port=5051, use_reloader=False)
#code finished.
