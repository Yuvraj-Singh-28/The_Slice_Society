import json
from io import BytesIO
from datetime import datetime
import re
import sqlite3

from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = 'mysecretkey'

DATABASE_NAME = 'slice_society.db'
TAX_RATE = 0.15
DISCOUNT_CODES = {
    'SLICE10': 0.10,
    'STUDENT15': 0.15,
    'PIZZA20': 0.20,
}


def initialise_database():
    """Create the database table needed for saved orders."""
    with sqlite3.connect(DATABASE_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                invoice_number TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                cart TEXT NOT NULL,
                totals TEXT NOT NULL
            )
            '''
        )
        conn.commit()


def load_data():
    """Load pizza data from the JSON file."""
    with open('data/pizza.json', 'r') as file:
        return json.load(file)


def load_addons():
    """Load add-on data if the add-ons JSON file has content."""
    try:
        with open('data/addons.json', 'r') as file:
            return json.load(file)
    except json.JSONDecodeError:
        return {}


def get_cart_items():
    """Return cart items with safe price and quantity values."""
    cart_items = session.get('cart', [])
    for item in cart_items:
        item['price'] = float(item['price'])
        item['quantity'] = int(item.get('quantity', 1))
    return cart_items


def calculate_cart_totals(cart, discount_code=''):
    """Calculate subtotal, discount, tax, and final total."""
    subtotal = sum(item['price'] * item['quantity'] for item in cart)
    discount_code = discount_code.strip().upper()
    discount_rate = DISCOUNT_CODES.get(discount_code, 0)
    discount_amount = subtotal * discount_rate
    taxable_total = subtotal - discount_amount
    tax = taxable_total * TAX_RATE
    total = taxable_total + tax

    return {
        'subtotal': round(subtotal, 2),
        'discount_code': discount_code,
        'discount_rate': discount_rate,
        'discount_amount': round(discount_amount, 2),
        'discount': round(discount_amount, 2),
        'discount_applied': discount_rate > 0,
        'tax': round(tax, 2),
        'total': round(total, 2),
    }


def build_invoice_text(invoice):
    """Build plain text for the downloadable invoice PDF."""
    lines = [
        'The Slice Society Invoice',
        '',
        f"Invoice number: {invoice['order_number']}",
        f"Date: {invoice['created_at']}",
        f"Customer: {invoice['customer']['name']}",
        f"Email: {invoice['customer']['email']}",
        f"Phone: {invoice['customer']['phone']}",
        f"Address: {invoice['customer']['address']}",
        '',
        'Items:',
    ]

    for item in invoice['items']:
        item_total = item['price'] * item['quantity']
        lines.append(
            f"- {item['name']}: "
            f"{item['quantity']} x ${item['price']:.2f} = ${item_total:.2f}"
        )

    lines.extend([
        '',
        f"Subtotal: ${invoice['totals']['subtotal']:.2f}",
    ])

    if invoice['totals']['discount_applied']:
        lines.append(
            f"Discount ({invoice['totals']['discount_code']}): "
            f"-${invoice['totals']['discount_amount']:.2f}"
        )

    lines.extend([
        f"Tax: ${invoice['totals']['tax']:.2f}",
        f"Total: ${invoice['totals']['total']:.2f}",
    ])

    return '\n'.join(lines)


def build_invoice_pdf(invoice):
    """Return a PDF invoice as bytes."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    y = 800

    for line in build_invoice_text(invoice).splitlines():
        pdf.drawString(50, y, line)
        y -= 20

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def validate_checkout_form(form):
    """Return a list of checkout validation error messages."""
    errors = []
    required_fields = [
        'name',
        'email',
        'phone',
        'address',
        'card',
        'expiry',
        'cvv',
    ]

    for field in required_fields:
        if not form.get(field, '').strip():
            errors.append('Please complete every checkout field.')
            break

    email = form.get('email', '').strip()
    phone_digits = re.sub(r'\D', '', form.get('phone', ''))
    card_digits = re.sub(r'\D', '', form.get('card', ''))
    cvv_digits = re.sub(r'\D', '', form.get('cvv', ''))
    expiry = form.get('expiry', '').strip()

    if email and '@' not in email:
        errors.append('Please enter a valid email address.')
    if phone_digits and len(phone_digits) < 8:
        errors.append('Please enter a valid phone number.')
    if card_digits and len(card_digits) != 16:
        errors.append('Card number must contain 16 digits.')
    if cvv_digits and len(cvv_digits) != 3:
        errors.append('CVV must contain 3 digits.')
    if expiry and not re.fullmatch(r'(0[1-9]|1[0-2])/[0-9]{2}', expiry):
        errors.append('Expiry date must use MM/YY format.')

    return errors


@app.route('/')
def index():
    """Display the home page."""
    return render_template('index.html')


@app.route('/history')
def history():
    """Display the restaurant history page."""
    return render_template('history.html')


@app.route('/menu')
def menu():
    """Display pizzas loaded from the JSON menu file."""
    pizzas = load_data()
    return render_template('menu.html', pizzas=pizzas)


@app.route('/cart')
def cart():
    """Display the cart with totals and any applied discount."""
    cart_items = get_cart_items()
    discount_code = session.get('discount_code', '')
    totals = calculate_cart_totals(cart_items, discount_code)
    return render_template('cart.html', cart_items=cart_items, totals=totals)


@app.route('/orders')
def orders():
    """Display saved orders from the database."""
    with sqlite3.connect(DATABASE_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders ORDER BY id DESC')
        saved_orders = cursor.fetchall()

    return render_template('orders.html', orders=saved_orders)


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    """Add a pizza to the shopping cart stored in the session."""
    pizza_name = request.form.get('pizza_name')
    pizza_price = request.form.get('pizza_price')
    pizzas = load_data()

    if pizza_name not in pizzas:
        flash('Invalid pizza selected.')
        return redirect(url_for('menu'))

    if 'cart' not in session:
        session['cart'] = []

    item_found = False
    for item in session['cart']:
        if item['name'] == pizza_name:
            item['quantity'] = item.get('quantity', 1) + 1
            item_found = True
            break

    if not item_found:
        session['cart'].append({
            'name': pizza_name,
            'price': float(pizza_price),
            'quantity': 1,
        })

    session.modified = True
    flash(f'Added {pizza_name} to cart!')
    return redirect(url_for('menu'))


@app.route('/apply_discount', methods=['POST'])
def apply_discount():
    """Store a valid discount code for the current order."""
    code = request.form.get('discount_code', '').upper().strip()

    if not code:
        session.pop('discount_code', None)
        flash('Discount removed.')
    elif code in DISCOUNT_CODES:
        session['discount_code'] = code
        flash(f'{code} discount applied.')
    else:
        flash('That discount code is not valid.')

    session.modified = True
    return redirect(request.referrer or url_for('cart'))


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    """Display checkout or create an invoice after successful validation."""
    cart_items = get_cart_items()
    if not cart_items:
        flash('Your cart is empty!')
        return redirect(url_for('menu'))

    discount_code = session.get('discount_code', '')
    totals = calculate_cart_totals(cart_items, discount_code)

    if request.method == 'POST':
        errors = validate_checkout_form(request.form)
        if errors:
            for error in errors:
                flash(error)
            return render_template(
                'checkout.html',
                cart_items=cart_items,
                totals=totals,
                form_data=request.form,
            )

        invoice_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        customer_name = request.form.get('name').strip().title()
        invoice_number = (
            f"INV_{customer_name.replace(' ', '_')}_"
            f"{invoice_date.replace(':', '-')}"
        )
        invoice = {
            'order_number': invoice_number,
            'created_at': invoice_date,
            'customer': {
                'name': customer_name,
                'email': request.form.get('email').strip(),
                'phone': request.form.get('phone').strip(),
                'address': request.form.get('address').strip(),
            },
            'items': cart_items,
            'totals': totals,
        }

        session['last_invoice'] = invoice
        session['cart'] = []
        session.pop('discount_code', None)
        session.modified = True

        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO orders(
                    invoice_number,
                    invoice_date,
                    customer_name,
                    cart,
                    totals
                )
                VALUES (?, ?, ?, ?, ?)
                ''',
                (
                    invoice_number,
                    invoice_date,
                    customer_name,
                    json.dumps(cart_items),
                    json.dumps(totals),
                ),
            )
            conn.commit()

        flash('Order placed successfully!')
        return redirect(url_for('invoice'))

    return render_template(
        'checkout.html',
        cart_items=cart_items,
        totals=totals,
        form_data={},
    )


@app.route('/invoice')
def invoice():
    """Display the most recent invoice."""
    last_invoice = session.get('last_invoice')
    if not last_invoice:
        flash('No invoice is available yet.')
        return redirect(url_for('menu'))
    return render_template('invoice.html', invoice=last_invoice)


@app.route('/download_invoice')
def download_invoice():
    """Download the latest invoice as a PDF."""
    invoice_data = session.get('last_invoice')

    if not invoice_data:
        flash('No invoice is available to download.')
        return redirect(url_for('menu'))

    invoice_pdf = build_invoice_pdf(invoice_data)
    filename = f"{invoice_data['order_number'].replace(':', '-')}.pdf"

    return Response(
        invoice_pdf,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@app.route('/remove_from_cart/<pizza_name>', methods=['POST'])
def remove_from_cart(pizza_name):
    """Remove one pizza type from the cart."""
    if 'cart' in session:
        session['cart'] = [
            item for item in session['cart']
            if item['name'] != pizza_name
        ]
        session.modified = True
        flash(f'Removed {pizza_name} from cart!')
    return redirect(url_for('cart'))


@app.route('/clear_cart', methods=['POST'])
def clear_cart():
    """Clear cart items and any discount from the session."""
    session.pop('cart', None)
    session.pop('discount_code', None)
    session.modified = True
    flash('Cart cleared!')
    return redirect(url_for('cart'))


if __name__ == '__main__':
    initialise_database()
    app.run(debug=True, port=5051)
