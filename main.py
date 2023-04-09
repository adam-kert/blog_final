import datetime

import flask
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
import forms
from forms import CreatePostForm, RegisterForm, LogInForm
from flask_gravatar import Gravatar
from functools import wraps


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


##CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    posts = db.relationship('BlogPost', back_populates='author')  # connecting post data with author
    comments = db.relationship('Comments', back_populates='comment_author')


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    author = db.relationship('User', back_populates='posts')
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = db.relationship('Comments', back_populates='parent_post')


class Comments(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    text = db.Column(db.Text, nullable=False)
    comment_author = db.relationship('User', back_populates='comments')
    post_id = db.Column(db.Integer, db.ForeignKey('blog_posts.id'))  # connecting comments to the blog post
    parent_post = db.relationship('BlogPost', back_populates='comments')


gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)


def admin_only(func):
    @wraps(func)
    def admin(*args, **kwargs):
        try:
            if current_user.id == 1:
                return func(*args, **kwargs)
            else:
                flask.abort(403, "you don't have the right")
        except AttributeError as e:
            print(e)
            flask.abort(code=403)
    return admin


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.get_or_404(User, int(user_id))
    except KeyError:
        return None


@app.route('/')
def get_all_posts():
    # db.create_all()
    posts = db.session.execute(db.select(BlogPost)).scalars()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user_name_exists = db.session.execute(db.select(User).where(User.name == request.form['name'])).scalar()
            if user_name_exists:
                flash(request.form['name'] + " is already taken.")
                return redirect(url_for('register'))
            user_email_exists = db.session.execute(db.select(User).where(User.email == request.form['email'])).scalar()
            if user_email_exists:
                flash('Email already in use. Please log in.')
                return redirect(url_for('login'))
            else:
                user = User()
                user.name = request.form['name']
                user.email = request.form['email']
                user.password = generate_password_hash(
                    method='pbkdf2:sha256',
                    password=request.form['password'],
                    salt_length=8)
                db.session.add(user)
                db.session.commit()
                login_user(user)
                return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LogInForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            user = db.session.execute(db.select(User).where(User.email == request.form['email'])).scalar()
            if user:
                if check_password_hash(pwhash=user.password,
                                       password=request.form['password']):
                    login_user(user)
                    return redirect(url_for('get_all_posts'))
                else:
                    flash('Invalid password or email')
                    return redirect(url_for('login'))
            else:
                flash('Invalid password or email')
                return redirect(url_for('login'))

    return render_template("login.html", form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    form = forms.Comment()
    requested_post = BlogPost.query.get(post_id)
    comments = db.session.execute(db.select(Comments).where(Comments.post_id == post_id)).scalars()
    if request.method == 'POST':
        if current_user.is_authenticated:
            if form.validate_on_submit():
                comment = Comments()
                comment.author_id = current_user.id
                comment.text = request.form['comment']
                comment.post_id = post_id
                db.session.add(comment)
                db.session.commit()
        else:
            flash('You are not authenticated. Please log in.')
            return redirect(url_for('login'))

    return render_template("post.html", post=requested_post, form=form, comments=comments)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.context_processor
def current_year():
    return {'year': datetime.date.today().strftime('%Y')}


@app.route("/new-post", methods=['GET', 'POST'])
@login_required
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.id,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=['GET', 'POST'])
@login_required
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author_id=post.author_id,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@login_required
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
    # app.run(debug=True)