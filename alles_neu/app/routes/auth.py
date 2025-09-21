from flask import Blueprint, render_template, request, redirect, url_for

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Login-Logik hier
        username = request.form['username']
        password = request.form['password']
        # Prüfen & weiterleiten
        return redirect(url_for('input.input_page'))
    return render_template('auth.html')
