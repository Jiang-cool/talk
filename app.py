from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import sqlite3
import os

# 尝试导入 PostgreSQL，如果失败则使用 SQLite
try:
    import psycopg2
    from urllib.parse import urlparse
    POSTGRES_AVAILABLE = True
    print("✅ PostgreSQL 驱动可用")
except ImportError:
    POSTGRES_AVAILABLE = False
    print("⚠️  PostgreSQL 驱动不可用，使用 SQLite")

app = Flask(__name__)
CORS(app)

# 数据库配置
def get_db_connection():
    """获取数据库连接 - 智能选择 PostgreSQL 或 SQLite"""
    database_url = os.environ.get('DATABASE_URL')
    
    print(f"🔧 数据库URL: {database_url}")
    
    # 如果配置了 DATABASE_URL 且 PostgreSQL 可用
    if database_url and POSTGRES_AVAILABLE:
        try:
            # 检查是否是 Railway 的变量引用格式
            if database_url.startswith('{{') and database_url.endswith('}}'):
                print("⚠️  检测到 Railway 变量引用格式")
                print("❌ Render 无法解析 Railway 的变量引用")
                print("🔄 使用 SQLite 数据库")
                conn = sqlite3.connect('database.db')
                conn.row_factory = sqlite3.Row
                return conn
            
            conn = psycopg2.connect(database_url, sslmode='require')
            print("✅ 连接到 PostgreSQL 数据库")
            return conn
        except Exception as e:
            print(f"❌ PostgreSQL 连接失败: {e}")
            print("🔄 回退到 SQLite 数据库")
    
    # 使用 SQLite（开发环境或 PostgreSQL 不可用）
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    print("✅ 连接到 SQLite 数据库")
    return conn

def init_db():
    """初始化数据库和表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 创建用户表
        if os.environ.get('DATABASE_URL'):
            # PostgreSQL 语法
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(100) NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (author_id) REFERENCES users (id)
                )
            ''')
        else:
            # SQLite 语法
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    author_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (author_id) REFERENCES users (id)
                )
            ''')
        
        conn.commit()
        print("✅ 数据库表创建成功")
        
        # 添加示例数据
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            if os.environ.get('DATABASE_URL'):
                # PostgreSQL 插入
                cursor.execute('INSERT INTO posts (title, content, author_id) VALUES (%s, %s, %s)',
                             ('欢迎来到论坛！', '这是一个欢迎帖子，欢迎大家一起交流！\n我是论坛的作者，这个论坛是我一手操办的。\n这里我就不多说了，愿大家使用快乐！\n如发现有问题或建议，可当面通知，亦可通过关于页面的电子邮箱向我发送邮件。\n愿大家常怀感恩之心，努力学习，报效祖国！\n  作者致辞', 1))
            else:
                # SQLite 插入
                cursor.execute('INSERT INTO posts (title, content, author_id) VALUES (?, ?, ?)',
                             ('欢迎来到论坛！', '这是一个欢迎帖子，欢迎大家一起交流！\n我是论坛的作者，这个论坛是我一手操办的。\n这里我就不多说了，愿大家使用快乐！\n如发现有问题或建议，可当面通知，亦可通过关于页面的电子邮箱向我发送邮件。\n愿大家常怀感恩之心，努力学习，报效祖国！\n  作者致辞', 1))
            
            conn.commit()
            print("✅ 示例数据添加成功")
            
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        conn.rollback()
    finally:
        conn.close()

# 静态文件服务
@app.route('/')
def serve_index():
    return send_from_directory('.', '登录.html')

@app.route('/<path:filename>')
def serve_static(filename):
    if filename.endswith('.html') or filename.endswith('.png'):
        return send_from_directory('.', filename)
    return '文件未找到', 404

# 注册接口
@app.route('/app/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        print(f'📨 收到注册请求: {data}')
        
        if not data or 'name' not in data or 'password' not in data:
            return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
        
        name = data['name']
        password = data['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()

        # 检查用户名是否已存在
        if os.environ.get('DATABASE_URL'):
            cursor.execute('SELECT id FROM users WHERE name = %s', (name,))
        else:
            cursor.execute('SELECT id FROM users WHERE name = ?', (name,))
            
        existing_user = cursor.fetchone()

        if existing_user:
            conn.close()
            return jsonify({'success': False, 'message': '用户名已存在'}), 400

        # 插入新用户
        if os.environ.get('DATABASE_URL'):
            cursor.execute('INSERT INTO users (name, password) VALUES (%s, %s) RETURNING id', (name, password))
            user_id = cursor.fetchone()[0]
        else:
            cursor.execute('INSERT INTO users (name, password) VALUES (?, ?)', (name, password))
            user_id = cursor.lastrowid
            
        conn.commit()
        conn.close()

        print(f'✅ 用户 {name} 注册成功，用户ID: {user_id}')
        return jsonify({
            'success': True, 
            'message': '注册成功', 
            'user_id': user_id
        }), 201
        
    except Exception as e:
        print(f'❌ 注册失败: {e}')
        return jsonify({'success': False, 'message': '注册失败'}), 500

# 获取所有用户接口
@app.route('/app/users', methods=['GET'])
def get_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users ORDER BY id')
        users = cursor.fetchall()
        
        users_list = []
        for user in users:
            users_list.append({
                'id': user[0],
                'name': user[1],
                'password': user[2]
            })
        
        conn.close()
        return jsonify({'success': True, 'data': users_list})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# 发布帖子接口
@app.route('/app/posts', methods=['POST'])
def create_post():
    try:
        data = request.get_json()
        print(f'📨 收到发帖请求: {data}')

        conn = get_db_connection()
        cursor = conn.cursor()
        
        if os.environ.get('DATABASE_URL'):
            cursor.execute('''
                INSERT INTO posts (title, content, author_id) VALUES (%s, %s, %s) RETURNING id
            ''', (data['title'], data['content'], data['author_id']))
            post_id = cursor.fetchone()[0]
        else:
            cursor.execute('''
                INSERT INTO posts (title, content, author_id) VALUES (?, ?, ?)
            ''', (data['title'], data['content'], data['author_id']))
            post_id = cursor.lastrowid
            
        conn.commit()
        conn.close()
        
        print(f'✅ 帖子发布成功，帖子ID: {post_id}')
        return jsonify({'success': True, 'message': '帖子发布成功', 'post_id': post_id}), 201
        
    except Exception as e:
        print(f'❌ 帖子发布失败: {e}')
        return jsonify({'success': False, 'message': '帖子发布失败'}), 500

# 获取帖子列表接口
@app.route('/app/posts')
def get_posts():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT 
                posts.id,
                posts.title,
                posts.content,
                posts.author_id,
                users.name as author_name,
                posts.created_at
            FROM posts
            JOIN users ON posts.author_id = users.id
            ORDER BY posts.created_at DESC
        ''')

        posts = cursor.fetchall()
        posts_list = []

        for post in posts:
            created_at = post[5]
            formatted_time = created_at
            
            if created_at:
                try:
                    if isinstance(created_at, str):
                        dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                        beijing_time = dt + timedelta(hours=8)
                        formatted_time = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
                    elif isinstance(created_at, datetime):
                        beijing_time = created_at + timedelta(hours=8)
                        formatted_time = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as time_error:
                    print(f"时间转换错误: {time_error}")
                    formatted_time = created_at

            content_preview = post[2]
            if len(content_preview) > 100:
                content_preview = content_preview[:100] + '...'

            posts_list.append({
                'id': post[0],
                'title': post[1],
                'content_preview': content_preview,
                'content': post[2],
                'author_id': post[3],
                'author_name': post[4],
                'created_at': formatted_time
            })

        conn.close()
        return jsonify({
            'success': True, 
            'data': posts_list,
            'count': len(posts_list)
        })

    except Exception as e:
        print(f'❌ 获取帖子列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500

# 获取单个帖子接口
@app.route('/app/posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if os.environ.get('DATABASE_URL'):
            cursor.execute('''
                SELECT 
                    posts.id,
                    posts.title,
                    posts.content,
                    posts.author_id,
                    users.name as author_name,
                    posts.created_at
                FROM posts
                JOIN users ON posts.author_id = users.id
                WHERE posts.id = %s
            ''', (post_id,))
        else:
            cursor.execute('''
                SELECT 
                    posts.id,
                    posts.title,
                    posts.content,
                    posts.author_id,
                    users.name as author_name,
                    posts.created_at
                FROM posts
                JOIN users ON posts.author_id = users.id
                WHERE posts.id = ?
            ''', (post_id,))
        
        post = cursor.fetchone()
        conn.close()
        
        if post is None:
            return jsonify({'success': False, 'message': '帖子未找到'}), 404

        created_at = post[5]
        formatted_time = created_at
            
        if created_at:
            try:
                if isinstance(created_at, str):
                    dt = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                    beijing_time = dt + timedelta(hours=8)
                    formatted_time = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(created_at, datetime):
                    beijing_time = created_at + timedelta(hours=8)
                    formatted_time = beijing_time.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as time_error:
                print(f"时间转换错误: {time_error}")
                formatted_time = created_at

        post_detail = {
            'id': post[0],
            'title': post[1],
            'content': post[2],
            'author_id': post[3],
            'author_name': post[4],
            'created_at': formatted_time
        }
        
        return jsonify({
            'success': True,
            'data': post_detail
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# 健康检查接口
@app.route('/app/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': '后端服务运行正常'})

# 添加启动代码
if __name__ == '__main__':
    # 初始化数据库
    init_db()
    
    # 配置端口
    port = int(os.environ.get('PORT', 50000))
    
    print(f"🚀 服务器启动在: http://0.0.0.0:{port}")
    print("🔗 可用接口:")
    print(f"   POST /app/register  - 用户注册")
    print(f"   GET  /app/users     - 获取用户列表")
    print(f"   GET  /app/health    - 健康检查")
    print(f"   POST /app/posts     - 发布帖子")
    print(f"   GET  /app/posts     - 查询帖子")
    
    # 启动Flask应用
    app.run(debug=False, port=port, host='0.0.0.0')
else:
    # 这是给 Vercel 使用的
    print("🔧 Vercel 环境初始化...")
    init_db()
