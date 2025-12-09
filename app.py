import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

# Инициализация приложения Flask
app = Flask(__name__)

# Конфигурация приложения
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
app.config['ITEMS_PER_PAGE'] = 12

# Создаем папку для загрузок если её нет
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'news'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'products'), exist_ok=True)

# Инициализация расширений
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'


# -------------------------------------------------------------------
# ФИЛЬТРЫ ДЛЯ ШАБЛОНОВ
# -------------------------------------------------------------------

@app.template_filter('format_date')
def format_date_filter(value, format='%d.%m.%Y'):
    """Фильтр для форматирования даты"""
    if value is None:
        return ""
    return value.strftime(format)


@app.template_filter('format_price')
def format_price_filter(value):
    """Фильтр для форматирования цены"""
    if value is None:
        return "0 ₽"
    try:
        return f"{value:,.2f} ₽".replace(',', ' ').replace('.', ',')
    except (TypeError, ValueError):
        return "0 ₽"


# -------------------------------------------------------------------
# МОДЕЛИ БАЗЫ ДАННЫХ
# -------------------------------------------------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<News {self.title}>'


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(300))
    category = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    stock_quantity = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Product {self.name}>'

    @property
    def in_stock(self):
        """Проверяет, есть ли товар в наличии"""
        return self.is_active and self.stock_quantity > 0


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_email = db.Column(db.String(120))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    status = db.Column(db.String(50), default='новый')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    product = db.relationship('Product', backref='orders')
    user = db.relationship('User', backref='orders')

    def __repr__(self):
        return f'<Order {self.id} - {self.customer_name}>'

    @property
    def total_price(self):
        """Вычисляемое свойство для общей суммы заказа"""
        if self.product:
            return self.product.price * self.quantity
        return 0


# -------------------------------------------------------------------
# ПОЛЬЗОВАТЕЛЬСКИЕ ЗАГРУЗЧИКИ
# -------------------------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# -------------------------------------------------------------------
# КОНТЕКСТНЫЕ ПРОЦЕССОРЫ (ДЛЯ ВСЕХ ШАБЛОНОВ)
# -------------------------------------------------------------------

@app.context_processor
def inject_models():
    """Внедряет модели в контекст всех шаблонов"""
    return dict(
        Order=Order,
        Product=Product,
        News=News,
        User=User
    )


# -------------------------------------------------------------------
# ОСНОВНЫЕ МАРШРУТЫ
# -------------------------------------------------------------------

@app.route('/')
def index():
    """Главная страница"""
    news = News.query.filter_by(is_published=True).order_by(News.created_at.desc()).limit(5).all()
    products = Product.query.filter_by(is_active=True).limit(8).all()
    return render_template('index.html', news=news, products=products)


@app.route('/news')
def news_list():
    """Список всех новостей"""
    page = request.args.get('page', 1, type=int)
    news = News.query.filter_by(is_published=True) \
        .order_by(News.created_at.desc()) \
        .paginate(page=page, per_page=10, error_out=False)
    return render_template('news.html', news=news)


@app.route('/news/<int:news_id>')
def news_detail(news_id):
    """Страница отдельной новости"""
    news_item = News.query.get_or_404(news_id)
    return render_template('news_detail.html', news=news_item)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Страница детального просмотра товара"""
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)


@app.route('/catalog')
def catalog():
    """Каталог товаров"""
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    in_stock = request.args.get('in_stock')

    query = Product.query

    if category:
        query = query.filter_by(category=category)
    if min_price:
        query = query.filter(Product.price >= min_price)
    if max_price:
        query = query.filter(Product.price <= max_price)
    if in_stock == '1':
        query = query.filter(Product.is_active == True, Product.stock_quantity > 0)
    else:
        query = query.filter_by(is_active=True)

    products = query.order_by(Product.created_at.desc()) \
        .paginate(page=page, per_page=app.config['ITEMS_PER_PAGE'], error_out=False)

    categories = db.session.query(Product.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]

    return render_template('catalog.html',
                           products=products,
                           categories=categories,
                           current_category=category,
                           in_stock=in_stock)


@app.route('/about')
def about():
    """Страница 'О нас'"""
    print("DEBUG: Маршрут /about вызван")
    return render_template('about.html')


@app.route('/contacts')
def contacts():
    """Страница 'Контакты'"""
    print("DEBUG: Маршрут /contacts вызван")
    return render_template('contacts.html')


# -------------------------------------------------------------------
# МАРШРУТЫ ДЛЯ ОФОРМЛЕНИЯ ЗАКАЗА
# -------------------------------------------------------------------

@app.route('/order/create/<int:product_id>', methods=['GET', 'POST'])
def create_order(product_id):
    """Создание заказа на товар"""
    product = Product.query.get_or_404(product_id)

    if not product.in_stock:
        flash('Этот товар временно отсутствует в наличии', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    if request.method == 'POST':
        customer_name = request.form.get('customer_name')
        customer_phone = request.form.get('customer_phone')
        customer_email = request.form.get('customer_email')
        quantity = request.form.get('quantity', 1, type=int)
        notes = request.form.get('notes', '')

        if not customer_name or not customer_phone:
            flash('Пожалуйста, заполните обязательные поля (имя и телефон)', 'danger')
            return redirect(url_for('create_order', product_id=product_id))

        if quantity < 1:
            quantity = 1

        if quantity > product.stock_quantity:
            flash(f'На складе осталось только {product.stock_quantity} шт. этого товара', 'warning')
            return redirect(url_for('create_order', product_id=product_id))

        order = Order(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            product_id=product_id,
            quantity=quantity,
            notes=notes,
            status='новый'
        )

        if current_user.is_authenticated:
            order.user_id = current_user.id
            if not customer_email and current_user.email:
                order.customer_email = current_user.email

        try:
            db.session.add(order)
            db.session.commit()
            flash(f'Заказ №{order.id} успешно оформлен! Мы свяжемся с вами в ближайшее время.', 'success')
            return redirect(url_for('order_success', order_id=order.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Произошла ошибка при создании заказа: {str(e)}', 'danger')
            return redirect(url_for('create_order', product_id=product_id))

    return render_template('order_create.html', product=product)


@app.route('/order/success/<int:order_id>')
def order_success(order_id):
    """Страница успешного оформления заказа"""
    order = Order.query.get_or_404(order_id)
    return render_template('order_success.html', order=order)


@app.route('/order/status/<int:order_id>')
def check_order_status(order_id):
    """Проверка статуса заказа"""
    order = Order.query.get_or_404(order_id)
    return render_template('order_status.html', order=order)


# -------------------------------------------------------------------
# АУТЕНТИФИКАЦИЯ
# -------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа в систему"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash('Вы успешно вошли в систему', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Страница регистрации"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Это имя пользователя уже занято', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Этот email уже используется', 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=email)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# -------------------------------------------------------------------
# ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ
# -------------------------------------------------------------------

@app.route('/profile')
@login_required
def profile():
    """Страница профиля пользователя"""
    user_orders = Order.query.filter_by(user_id=current_user.id) \
        .order_by(Order.created_at.desc()) \
        .all()
    return render_template('profile.html', orders=user_orders)


# -------------------------------------------------------------------
# АДМИН-ПАНЕЛЬ
# -------------------------------------------------------------------

@app.route('/admin')
@login_required
def admin_panel():
    """Админ-панель (главная)"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    orders_count = Order.query.count()
    products_count = Product.query.filter_by(is_active=True).count()
    news_count = News.query.filter_by(is_published=True).count()
    users_count = User.query.count()
    new_orders_count = Order.query.filter_by(status='новый').count()

    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()

    return render_template('admin/index.html',
                           orders_count=orders_count,
                           products_count=products_count,
                           news_count=news_count,
                           users_count=users_count,
                           new_orders_count=new_orders_count,
                           recent_orders=recent_orders)


@app.route('/admin/news')
@login_required
def admin_news():
    """Управление новостями в админке"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)
    news_list = News.query.order_by(News.created_at.desc()) \
        .paginate(page=page, per_page=20, error_out=False)

    return render_template('admin/news.html', news=news_list)


@app.route('/admin/news/new', methods=['GET', 'POST'])
@login_required
def admin_create_news():
    """Создание новой новости"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        image = request.files.get('image')
        is_published = request.form.get('is_published') == '1'

        if not title or not content:
            flash('Заполните обязательные поля', 'danger')
            return redirect(url_for('admin_create_news'))

        news = News(title=title, content=content, is_published=is_published)

        if image:
            filename = secure_filename(image.filename)
            # Создаем уникальное имя файла
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'news', filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image.save(image_path)
            news.image = f'uploads/news/{filename}'

        db.session.add(news)
        db.session.commit()

        flash('Новость успешно создана', 'success')
        return redirect(url_for('admin_news'))

    return render_template('admin/create_news.html')


@app.route('/admin/news/edit/<int:news_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_news(news_id):
    """Редактирование новости"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    news_item = News.query.get_or_404(news_id)

    if request.method == 'POST':
        news_item.title = request.form.get('title')
        news_item.content = request.form.get('content')
        news_item.is_published = request.form.get('is_published') == '1'

        # Обработка загрузки нового изображения
        image = request.files.get('image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'news', filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image.save(image_path)
            news_item.image = f'uploads/news/{filename}'

        # Удаление изображения
        delete_image = request.form.get('delete_image')
        if delete_image == '1':
            news_item.image = None

        db.session.commit()
        flash('Новость успешно обновлена', 'success')
        return redirect(url_for('admin_news'))

    return render_template('admin/edit_news.html', news=news_item)


@app.route('/admin/news/delete/<int:news_id>', methods=['POST'])
@login_required
def admin_delete_news(news_id):
    """Удаление новости"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    news_item = News.query.get_or_404(news_id)

    try:
        db.session.delete(news_item)
        db.session.commit()
        flash('Новость успешно удалена', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении новости: {str(e)}', 'danger')

    return redirect(url_for('admin_news'))


@app.route('/admin/orders')
@login_required
def admin_orders():
    """Управление заказами в админке"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')

    query = Order.query

    if status_filter:
        query = query.filter_by(status=status_filter)

    orders = query.order_by(Order.created_at.desc()) \
        .paginate(page=page, per_page=20, error_out=False)

    new_orders_count = Order.query.filter_by(status='новый').count()

    return render_template('admin/orders.html',
                           orders=orders,
                           current_status=status_filter,
                           new_orders_count=new_orders_count)


@app.route('/admin/order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def admin_order_detail(order_id):
    """Детальный просмотр заказа в админке"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    order = Order.query.get_or_404(order_id)

    if request.method == 'POST':
        new_status = request.form.get('status')
        admin_notes = request.form.get('admin_notes', '')

        if new_status and new_status in ['новый', 'в обработке', 'выполнен', 'отменен']:
            order.status = new_status

        if admin_notes:
            if order.notes:
                order.notes += f"\n[Админ {datetime.now().strftime('%d.%m.%Y %H:%M')}]: {admin_notes}"
            else:
                order.notes = f"[Админ {datetime.now().strftime('%d.%m.%Y %H:%M')}]: {admin_notes}"

        db.session.commit()
        flash('Статус заказа обновлен', 'success')
        return redirect(url_for('admin_order_detail', order_id=order_id))

    return render_template('admin/order_detail.html', order=order)


@app.route('/admin/products')
@login_required
def admin_products():
    """Управление товарами в админке"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)
    products = Product.query.order_by(Product.created_at.desc()) \
        .paginate(page=page, per_page=20, error_out=False)

    return render_template('admin/products.html', products=products)


@app.route('/admin/product/new', methods=['GET', 'POST'])
@login_required
def admin_create_product():
    """Создание нового товара"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = request.form.get('price', type=float)
        category = request.form.get('category')
        stock_quantity = request.form.get('stock_quantity', 10, type=int)
        image = request.files.get('image')

        product = Product(
            name=name,
            description=description,
            price=price,
            category=category,
            stock_quantity=stock_quantity,
            is_active=True
        )

        if image:
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'products', filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image.save(image_path)
            product.image = f'uploads/products/{filename}'

        db.session.add(product)
        db.session.commit()

        flash('Товар успешно создан', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/create_product.html')


@app.route('/admin/product/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_product(product_id):
    """Редактирование товара"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = request.form.get('price', type=float)
        product.category = request.form.get('category')
        product.stock_quantity = request.form.get('stock_quantity', 10, type=int)
        product.is_active = request.form.get('is_active') == '1'

        # Обработка загрузки нового изображения
        image = request.files.get('image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], 'products', filename)
            os.makedirs(os.path.dirname(image_path), exist_ok=True)
            image.save(image_path)
            product.image = f'uploads/products/{filename}'

        # Удаление изображения
        delete_image = request.form.get('delete_image')
        if delete_image == '1':
            product.image = None

        db.session.commit()
        flash('Товар успешно обновлен', 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/edit_product.html', product=product)


@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@login_required
def admin_delete_product(product_id):
    """Удаление товара"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    product = Product.query.get_or_404(product_id)

    try:
        # Проверяем, есть ли заказы на этот товар
        orders_count = Order.query.filter_by(product_id=product_id).count()
        if orders_count > 0:
            flash(f'Нельзя удалить товар, так как на него есть {orders_count} заказ(ов)', 'danger')
            return redirect(url_for('admin_products'))

        db.session.delete(product)
        db.session.commit()
        flash('Товар успешно удален', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении товара: {str(e)}', 'danger')

    return redirect(url_for('admin_products'))


@app.route('/admin/product/toggle/<int:product_id>', methods=['POST'])
@login_required
def admin_toggle_product(product_id):
    """Включение/выключение товара"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()

    status = "включен" if product.is_active else "выключен"
    flash(f'Товар "{product.name}" {status}', 'success')
    return redirect(url_for('admin_products'))


@app.route('/admin/users')
@login_required
def admin_users():
    """Управление пользователями в админке"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()) \
        .paginate(page=page, per_page=20, error_out=False)

    return render_template('admin/users.html', users=users)


# -------------------------------------------------------------------
# API ДЛЯ AJAX
# -------------------------------------------------------------------

@app.route('/api/products')
def api_products():
    """API для получения товаров (JSON)"""
    products = Product.query.filter_by(is_active=True).all()
    result = []
    for product in products:
        result.append({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'category': product.category,
            'in_stock': product.in_stock,
            'stock_quantity': product.stock_quantity,
            'image': url_for('static', filename=product.image) if product.image else None
        })
    return jsonify(result)


@app.route('/api/search')
def api_search():
    """API для поиска товаров"""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])

    products = Product.query.filter(
        Product.name.ilike(f'%{query}%') |
        Product.description.ilike(f'%{query}%')
    ).limit(10).all()

    result = []
    for product in products:
        result.append({
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'url': url_for('product_detail', product_id=product.id),
            'in_stock': product.in_stock
        })

    return jsonify(result)


# -------------------------------------------------------------------
# ОБРАБОТЧИКИ ОШИБОК
# -------------------------------------------------------------------

@app.errorhandler(404)
def page_not_found(error):
    """Обработчик ошибки 404"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Обработчик ошибки 500"""
    db.session.rollback()
    return render_template('500.html'), 500


# -------------------------------------------------------------------
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ
# -------------------------------------------------------------------

def init_database():
    """Инициализация базы данных с тестовыми данными"""
    with app.app_context():
        # Удаляем старую БД и создаем новую
        db.drop_all()
        db.create_all()

        # Администратор
        admin = User(
            username='admin',
            email='admin@example.com',
            is_admin=True
        )
        admin.set_password('admin123')
        db.session.add(admin)

        # Тестовый пользователь
        test_user = User(
            username='testuser',
            email='test@example.com',
            is_admin=False
        )
        test_user.set_password('test123')
        db.session.add(test_user)

        # Тестовые товары (с полями для изображений)
        test_products = [
            Product(
                name='Ноутбук HP Pavilion',
                description='Мощный ноутбук для работы и игр.',
                price=69999.99,
                category='Электроника',
                stock_quantity=5,
                is_active=True
            ),
            Product(
                name='Смартфон Samsung Galaxy',
                description='Флагманский смартфон с камерой 108 МП.',
                price=54999.50,
                category='Электроника',
                stock_quantity=0,
                is_active=True
            ),
            Product(
                name='Наушники Sony WH-1000XM4',
                description='Беспроводные наушники с шумоподавлением.',
                price=24999.00,
                category='Аксессуары',
                stock_quantity=10,
                is_active=True
            ),
            Product(
                name='Книга "Python для начинающих"',
                description='Полное руководство по Python.',
                price=1599.99,
                category='Книги',
                stock_quantity=20,
                is_active=True
            ),
        ]

        for product in test_products:
            db.session.add(product)

        # Тестовые новости (с полями для изображений)
        test_news = [
            News(
                title='Открытие нового магазина',
                content='Мы рады сообщить об открытии нового магазина!',
                is_published=True
            ),
            News(
                title='Специальные скидки на технику',
                content='Только в декабре скидки до 30%!',
                is_published=True
            ),
        ]

        for news in test_news:
            db.session.add(news)

        db.session.commit()
        print('✅ База данных успешно инициализирована')
        print('✅ НЕ созданы тестовые заказы - база чистая')
        print('📸 ВНИМАНИЕ: Добавьте изображения для товаров и новостей через админку')


# -------------------------------------------------------------------
# ЗАПУСК ПРИЛОЖЕНИЯ
# -------------------------------------------------------------------

# Инициализация базы данных
init_database()

if __name__ == '__main__':
    print('\n' + '=' * 50)
    print('🚀 Flask приложение запущено!')
    print('🌐 Откройте в браузере: http://localhost:5000')
    print('👑 Админ панель: http://localhost:5000/admin')
    print('👤 Логин администратора: admin / admin123')
    print('👤 Тестовый пользователь: testuser / test123')
    print('📞 Страница контактов: http://localhost:5000/contacts')
    print('📦 База заказов чистая - без тестовых данных')
    print('📸 ДЛЯ ИЗОБРАЖЕНИЙ:')
    print('   1. Зайдите в админку: http://localhost:5000/admin')
    print('   2. Добавьте изображения через формы создания/редактирования')
    print('   3. Для товаров: /admin/products → Редактировать товар')
    print('   4. Для новостей: /admin/news → Редактировать новость')
    print('=' * 50 + '\n')

    app.run(debug=True, host='0.0.0.0', port=5000)