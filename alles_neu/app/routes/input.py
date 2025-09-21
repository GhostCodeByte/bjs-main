from flask import Blueprint, render_template

input_bp = Blueprint('input', __name__, template_folder='../templates')

@input_bp.route('/input')
def input_page():
    return render_template('input.html')
