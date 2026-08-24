import json
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, session, flash, redirect, url_for, Response
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'mysecretkey'

#
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/menu')
def menu():
    with open('data/pizza.json', 'r') as f:
        pizzas = json.load(f)
    return render_template('menu.html', pizzas=pizzas)

@app.route('/cart')
def cart():
    cart_items = session.get('cart', [])
    # Ensure prices are floats and quantities exist
    for item in cart_items:
        item['price'] = float(item['price'])
        if 'quantity' not in item:
            item['quantity'] = 1
    total = sum(item['price'] * item.get('quantity', 1) for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)
                                                                                                
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    pizza_name = request.form.get('pizza_name')
    pizza_price = request.form.get('pizza_price')
                               
    if 'cart' not in session:
        session['cart'] = []
                 
    # Check if item already exists in cart
    item_found = False
    for item in session['cart']:
        if item['name'] == pizza_name:
            item['quantity'] = item.get('quantity', 1) + 1
            item_found = True
            break
    
    # If item doesn't exist, add it with quantity 1
    if not item_found:
        session['cart'].append({'name': pizza_name, 'price': float(pizza_price), 'quantity': 1})
    
    session.modified = True
    
    flash(f'Added {pizza_name} to cart!')
    return redirect(url_for('menu'))

@app.route('/checkout')
def checkout():
    cart_items = session.get('cart', [])
    if not cart_items:
        flash('Your cart is empty!')
        return redirect(url_for('menu'))
    # Ensure prices are floats and quantities exist
    for item in cart_items:
        item['price'] = float(item['price'])
        if 'quantity' not in item:
            item['quantity'] = 1
    total = sum(item['price'] * item.get('quantity', 1) for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/remove_from_cart/<pizza_name>', methods=['POST'])
def remove_from_cart(pizza_name):
    if 'cart' in session:
        session['cart'] = [item for item in session['cart'] if item['name'] != pizza_name]
        session.modified = True
        flash(f'Removed {pizza_name} from cart!')
    return redirect(url_for('cart'))

@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    session['cart'] = []
    session.modified = True
    flash('Cart cleared!')
    return redirect(url_for('cart'))


# last line of code
if __name__ == '__main__':
    app.run(debug=True, port=5051)
#code finished.






