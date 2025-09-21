from flask import Blueprint, render_template, request, redirect, url_for, session, flash

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        discipline = request.form.get('discipline')
        password = request.form.get('password')

        if password == "1234":
            session['is_logged_in'] = True
            session['discipline'] = discipline

            return redirect(url_for('input.input_page'))
        else:
            flash('Ungültige Zugangsdaten.', 'error')
            return render_template('auth.html'), 401

    if session.get('is_logged_in'):
        return redirect(url_for('input.input_page'))
    return render_template('auth.html')
