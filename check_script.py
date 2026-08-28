from constants import NAV_BY_SCREEN
from app import app
print("NAV_BY_SCREEN:", NAV_BY_SCREEN.get("import-review"))
html = app.test_client().get("/screens/import-review").data.decode("utf-8")
print("Count of aria-current:", html.count('aria-current="page"'))

admin_idx = html.find("Administration")
if admin_idx != -1:
    admin_ctx = html[max(0, admin_idx - 150): min(len(html), admin_idx + 150)]
    print("Administration context has nav-link active:", 'class="nav-link active"' in admin_ctx)
else:
    print("Administration not found")

reg_idx = html.find("Regulation Library")
if reg_idx != -1:
    reg_ctx = html[max(0, reg_idx - 150): min(len(html), reg_idx + 150)]
    print("Regulation Library context has nav-link active:", 'class="nav-link active"' in reg_ctx)
else:
    print("Regulation Library not found")
