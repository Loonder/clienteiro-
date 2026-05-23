from flask import Flask
from core.auth import hash_password, check_password, login_required

def test_hash_password():
    raw = 'password123'
    hashed = hash_password(raw)
    assert isinstance(hashed, str)
    assert hashed
    assert hashed != raw
    assert check_password(raw, hashed) is True

def test_check_password_success():
    raw = 'password123'
    hashed = hash_password(raw)
    assert check_password(raw, hashed) is True

def test_check_password_failure():
    hashed = hash_password('correct')
    assert check_password('wrong', hashed) is False

def test_login_required_decorator():
    app = Flask(__name__)
    app.secret_key = 'test'
    
    @app.route('/protected')
    @login_required
    def protected():
        return 'success'

    with app.test_client() as client:
        # Should redirect to login if no session
        res = client.get('/protected')
        assert res.status_code == 302
        assert '/login' in res.location

        # Should work with session
        with client.session_transaction() as sess:
            sess['gestor_id'] = 1
        res = client.get('/protected')
        assert res.status_code == 200
        assert b'success' in res.data
