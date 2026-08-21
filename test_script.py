from app import app
client = app.test_client()
res = client.get('/screens/calculation-review')
html = res.data.decode('utf-8')
print('Status Code:', res.status_code)
print('Contains readiness-score warning:', 'readiness-score warning' in html)
print('Contains No assessment selected:', 'No assessment selected' in html)
print('Contains background: #fff8e7 (not expected):', 'background: #fff8e7' in html)
print('Contains disabled aria-disabled:', 'disabled' in html and 'aria-disabled' in html)
