import os
import logging

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_required, login_user, logout_user, current_user

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
# create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)  # needed for url_for to generate with https

# Configure PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Configure file uploads
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images', 'products')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# User loader function
@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Helper functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Import models here to avoid circular imports
    import models  # noqa: F401
    db.create_all()
    
    # Import models
    from models import Category, MenuItem, User
    
    # Create admin user if it doesn't exist
    if not User.query.filter_by(username="brendonguedes").first():
        admin_user = User(username="brendonguedes", is_admin=True)
        admin_user.set_password("2010aA@aaa")  # Updated credentials
        db.session.add(admin_user)
        db.session.commit()
        logging.debug("Admin user created")
    
    # Import and create sample data only if the tables are empty
    if not Category.query.first():
        logging.debug("Creating sample categories and menu items")
        
        # Create categories
        tradicional = Category(name="Tradicional", description="Clássicos que nunca saem de moda")
        gourmet = Category(name="Gourmet", description="Combinações exclusivas com ingredientes premium")
        vegetariano = Category(name="Vegetariano", description="Opções saborosas sem carne")
        
        db.session.add_all([tradicional, gourmet, vegetariano])
        db.session.commit()
        
        # Create menu items
        menu_items = [
            # Traditional hot dogs
            MenuItem(
                name="Clássico Brasileiro",
                description="Salsicha artesanal, molho de tomate caseiro, milho, ervilha, batata palha e maionese",
                price=14.90,
                category_id=tradicional.id,
                featured=True
            ),
            MenuItem(
                name="Rústico Simples",
                description="Salsicha artesanal, mostarda, ketchup e cebola caramelizada",
                price=12.90,
                category_id=tradicional.id
            ),
            MenuItem(
                name="Cachorro Quente Completo",
                description="Salsicha artesanal, molho de tomate, queijo, bacon, milho, ervilha, batata palha e maionese",
                price=16.90,
                category_id=tradicional.id,
                featured=True
            ),
            
            # Gourmet hot dogs
            MenuItem(
                name="Rústico Especial",
                description="Salsicha artesanal de cordeiro, molho de vinho tinto, queijo brie derretido e rúcula",
                price=24.90,
                category_id=gourmet.id,
                featured=True
            ),
            MenuItem(
                name="Mediterrâneo",
                description="Linguiça artesanal de frango, homus, tomate confitado e hortelã",
                price=22.90,
                category_id=gourmet.id
            ),
            MenuItem(
                name="Hot Dog Trufado",
                description="Salsicha artesanal bovina, cogumelos salteados, queijo gruyère e maionese trufada",
                price=28.90,
                category_id=gourmet.id,
                featured=True
            ),
            
            # Vegetarian hot dogs
            MenuItem(
                name="Veggie Dog",
                description="Salsicha de soja, guacamole, pico de gallo e coentro",
                price=18.90,
                category_id=vegetariano.id,
                featured=True
            ),
            MenuItem(
                name="Portobello Rústico",
                description="Cogumelo portobello grelhado, queijo coalho, chimichurri e cebola crispy",
                price=19.90,
                category_id=vegetariano.id
            )
        ]
        
        db.session.add_all(menu_items)
        db.session.commit()
        
        logging.debug("Sample data created successfully")

# Create image upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Public routes
@app.route('/')
def home():
    """Home page route"""
    from models import MenuItem, SiteContent
    featured_items = MenuItem.query.filter_by(featured=True).all()
    site_content = SiteContent.query.first()
    if not site_content:
        site_content = SiteContent(home_description="Somos uma casa especializada em cachorros-quentes artesanais...")
        db.session.add(site_content)
        db.session.commit()
    return render_template('index.html', featured_items=featured_items, site_content=site_content)

@app.route('/menu')
def menu():
    """Menu page route"""
    from models import Category
    categories = Category.query.all()
    return render_template('menu.html', categories=categories)

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login route"""
    if current_user.is_authenticated:
        return redirect(url_for('admin'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        from models import User
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('admin'))
        else:
            flash('Credenciais inválidas. Por favor, tente novamente.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout route"""
    logout_user()
    return redirect(url_for('home'))

# Admin routes
@app.route('/admin')
@login_required
def admin():
    """Admin dashboard"""
    from models import MenuItem, Category, SiteContent
    items = MenuItem.query.all()
    categories = Category.query.all()
    site_content = SiteContent.query.first()
    if not site_content:
        site_content = SiteContent(home_description="Somos uma casa especializada em cachorros-quentes artesanais...")
        db.session.add(site_content)
        db.session.commit()
    return render_template('admin.html', items=items, categories=categories, site_content=site_content)

@app.route('/admin/site-content/update', methods=['POST'])
@login_required
def update_site_content():
    """Update site content"""
    from models import SiteContent
    data = request.get_json()
    site_content = SiteContent.query.first()
    if site_content and data.get('home_description'):
        site_content.home_description = data['home_description']
        db.session.commit()
        return {'success': True}
    return {'success': False}, 400

@app.route('/admin/item/add', methods=['GET', 'POST'])
@login_required
def add_item():
    """Add menu item route"""
    from models import MenuItem, Category
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price').replace(',', '.'))
        category_id = request.form.get('category_id')
        featured = 'featured' in request.form
        
        image = None
        image_file = request.files.get('image')
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            image = os.path.join('images', 'products', filename)
        
        new_item = MenuItem(
            name=name,
            description=description,
            price=price,
            category_id=category_id,
            featured=featured,
            image=image
        )
        
        db.session.add(new_item)
        db.session.commit()
        
        flash('Item adicionado com sucesso!', 'success')
        return redirect(url_for('admin'))
    
    categories = Category.query.all()
    return render_template('add_item.html', categories=categories)

@app.route('/admin/item/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    """Edit menu item route"""
    from models import MenuItem, Category
    
    item = MenuItem.query.get_or_404(item_id)
    
    if request.method == 'POST':
        item.name = request.form.get('name')
        item.description = request.form.get('description')
        item.price = float(request.form.get('price').replace(',', '.'))
        item.category_id = request.form.get('category_id')
        item.featured = 'featured' in request.form
        
        image_file = request.files.get('image')
        if image_file and allowed_file(image_file.filename):
            filename = secure_filename(image_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(filepath)
            item.image = os.path.join('images', 'products', filename)
        
        db.session.commit()
        
        flash('Item atualizado com sucesso!', 'success')
        return redirect(url_for('admin'))
    
    categories = Category.query.all()
    return render_template('edit_item.html', item=item, categories=categories)

@app.route('/admin/item/<int:item_id>/update', methods=['POST'])
@login_required
def update_item_field(item_id):
    """Update item field route"""
    from models import MenuItem
    
    item = MenuItem.query.get_or_404(item_id)
    data = request.get_json()
    
    if data.get('field') in ['name', 'description']:
        setattr(item, data['field'], data['value'])
        db.session.commit()
        return {'success': True}
    
    return {'success': False}, 400

@app.route('/admin/item/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item(item_id):
    """Delete menu item route"""
    from models import MenuItem
    
    item = MenuItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    
    flash('Item excluído com sucesso!', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
