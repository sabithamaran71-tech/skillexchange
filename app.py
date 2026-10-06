from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "skill_exchange_secret_key"

DATABASE = "skill_exchange.db"


# ---------- DATABASE ----------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            teach_skill TEXT,
            learn_skill TEXT
        )

    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            status TEXT DEFAULT 'pending'
        )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS learning_resources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id INTEGER,
        student_id INTEGER,
        title TEXT NOT NULL,
        link TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            message TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
def remove_duplicate_connections():

    conn = get_db()

    conn.execute("""
        DELETE FROM connections
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM connections
            GROUP BY
                CASE
                    WHEN sender_id < receiver_id THEN sender_id
                    ELSE receiver_id
                END,
                CASE
                    WHEN sender_id < receiver_id THEN receiver_id
                    ELSE sender_id
                END
        )
    """)

    conn.commit()
    conn.close()

# ---------- HOME ----------

@app.route("/")
def home():
    return render_template("index.html")


# ---------- REGISTER ----------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        teach_skill = request.form["teach_skill"]
        learn_skill = request.form["learn_skill"]

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO users
                (name, email, password, teach_skill, learn_skill)
                VALUES (?, ?, ?, ?, ?)
            """, (name, email, password, teach_skill, learn_skill))

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return "Email already registered!"

        conn.close()

        return redirect("/login")

    return render_template("register.html")


# ---------- LOGIN ----------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute("""
            SELECT * FROM users
            WHERE email = ? AND password = ?
        """, (email, password)).fetchone()

        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect("/dashboard")

        return "Invalid email or password!"

    return render_template("login.html")


# ---------- DASHBOARD ----------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    user = conn.execute("""
        SELECT * FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    conn.close()

    return render_template("dashboard.html", user=user)
@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":

        name = request.form["name"]
        teach_skill = request.form["teach_skill"]
        learn_skill = request.form["learn_skill"]

        conn.execute("""
            UPDATE users
            SET name = ?, teach_skill = ?, learn_skill = ?
            WHERE id = ?
        """, (
            name,
            teach_skill,
            learn_skill,
            session["user_id"]
        ))

        conn.commit()
        conn.close()

        session["user_name"] = name

        return redirect("/dashboard")

    user = conn.execute("""
        SELECT * FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    conn.close()

    return render_template(
        "edit_profile.html",
        user=user
    )

# ---------- MATCHES ----------

@app.route("/matches")
def matches():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    current_user = conn.execute("""
        SELECT * FROM users
        WHERE id = ?
    """, (session["user_id"],)).fetchone()

    users = conn.execute("""
        SELECT * FROM users
        WHERE id != ?
        ORDER BY
        CASE
            WHEN LOWER(teach_skill) = LOWER(?) THEN 0
            ELSE 1
        END
    """, (
        session["user_id"],
        current_user["learn_skill"]
    )).fetchall()

    conn.close()

    return render_template(
        "matches.html",
        users=users,
        current_user=current_user
    )
# ---------- CONNECT ----------
@app.route("/connect/<int:user_id>")
def connect(user_id):

    if "user_id" not in session:
        return redirect("/login")

    sender_id = session["user_id"]

    if sender_id == user_id:
        return redirect("/matches")

    conn = get_db()

    existing = conn.execute("""
        SELECT * FROM connections
        WHERE
        (sender_id = ? AND receiver_id = ?)
        OR
        (sender_id = ? AND receiver_id = ?)
    """, (sender_id, user_id, user_id, sender_id)).fetchone()

    if not existing:
        conn.execute("""
            INSERT INTO connections
            (sender_id, receiver_id, status)
            VALUES (?, ?, 'pending')
        """, (sender_id, user_id))

        conn.commit()

    conn.close()

    return redirect("/dashboard")
@app.route("/requests")
def requests():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    requests = conn.execute("""
        SELECT connections.id,
               users.name,
               users.teach_skill,
               users.learn_skill
        FROM connections
        JOIN users
        ON connections.sender_id = users.id
        WHERE connections.receiver_id = ?
        AND connections.status = 'pending'
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template("requests.html", requests=requests)
# ---------- MY CONNECTIONS ----------

@app.route("/connections")
def connections():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    connections = conn.execute("""
        SELECT users.id, users.name, users.email, users.teach_skill, users.learn_skill
        FROM connections
        JOIN users
        ON (
            (connections.sender_id = ? AND users.id = connections.receiver_id)
            OR
            (connections.receiver_id = ? AND users.id = connections.sender_id)
        )
        WHERE connections.status = 'accepted'
    """, (session["user_id"], session["user_id"])).fetchall()

    conn.close()

    return render_template("connections.html", connections=connections)
# ---------- LEARNING ROOM ----------

@app.route("/learn/<int:user_id>")
def learn(user_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    partner = conn.execute("""
        SELECT * FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    if not partner:
        conn.close()
        return redirect("/connections")

    resources = conn.execute("""
        SELECT * FROM learning_resources
        WHERE teacher_id = ? AND student_id = ?
    """, (partner["id"], session["user_id"])).fetchall()
    messages = conn.execute("""
    SELECT messages.*, users.name
    FROM messages
    JOIN users ON messages.sender_id = users.id
    WHERE
    (sender_id = ? AND receiver_id = ?)
    OR
    (sender_id = ? AND receiver_id = ?)
    ORDER BY messages.id
""", (
    session["user_id"],
    partner["id"],
    partner["id"],
    session["user_id"]
)).fetchall()
    conn.close()

    return render_template(
        "learning.html",
        partner=partner,
        resources=resources,
        messages=messages
    )
@app.route("/add-resource/<int:student_id>", methods=["POST"])
def add_resource(student_id):

    if "user_id" not in session:
        return redirect("/login")

    title = request.form["title"]
    link = request.form["link"]

    conn = get_db()

    conn.execute("""
        INSERT INTO learning_resources
        (teacher_id, student_id, title, link)
        VALUES (?, ?, ?, ?)
    """, (
        session["user_id"],
        student_id,
        title,
        link
    ))

    conn.commit()
    conn.close()

    return redirect("/learn/" + str(student_id))
@app.route("/accept/<int:request_id>")
def accept(request_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute("""
        UPDATE connections
        SET status = 'accepted'
        WHERE id = ? AND receiver_id = ?
    """, (request_id, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/requests")


@app.route("/reject/<int:request_id>")
def reject(request_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    conn.execute("""
        DELETE FROM connections
        WHERE id = ? AND receiver_id = ?
    """, (request_id, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/requests")
@app.route("/delete-resource/<int:resource_id>")
def delete_resource(resource_id):

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    resource = conn.execute("""
        SELECT * FROM learning_resources
        WHERE id = ?
    """, (resource_id,)).fetchone()

    if resource:

        conn.execute("""
            DELETE FROM learning_resources
            WHERE id = ?
        """, (resource_id,))

        conn.commit()

    conn.close()

    return redirect("/connections")
@app.route("/send-message/<int:user_id>", methods=["POST"])
def send_message(user_id):

    if "user_id" not in session:
        return redirect("/login")

    message = request.form["message"]

    conn = get_db()

    conn.execute("""
        INSERT INTO messages
        (sender_id, receiver_id, message)
        VALUES (?, ?, ?)
    """, (session["user_id"], user_id, message))

    conn.commit()
    conn.close()

    return redirect("/learn/" + str(user_id))
# ---------- LOGOUT ----------

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ---------- RUN ----------

if __name__ == "__main__":
    create_database()
    remove_duplicate_connections()
    app.run(debug=True)