from flask import Flask, request, jsonify
import sqlite3
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:4200"}})
CORS(app)
DATABASE = "database.db"

# Fonction pour exécuter des requêtes SQLite
def query_db(query, args=(), one=False, commit=False):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(query, args)
    if commit:
        conn.commit()
        conn.close()
        return
    rv = cursor.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv


# Route de connexion
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
    if user and check_password_hash(user['password'], password):
        return jsonify({"message": "Connexion réussie", "user_id": user['id']})
    return jsonify({"error": "Email ou mot de passe incorrect"}), 401


# Route pour créer un utilisateur
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = generate_password_hash(data.get('password'))

    try:
        query_db("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                 (username, email, password), commit=True)
        return jsonify({"message": "Utilisateur créé avec succès"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email ou nom d'utilisateur déjà utilisé"}), 400


# Route pour supprimer un message
@app.route('/messages/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    query_db("DELETE FROM messages WHERE id = ?", (message_id,), commit=True)
    return jsonify({"message": "Message supprimé avec succès"})




@app.route('/chats', methods=['POST'])
def create_chat():
    try:
        data = request.json
        user1_id = data.get('user1_id')
        user2_id = data.get('user2_id')

        if not user1_id or not user2_id:
            return jsonify({"error": "Les IDs des utilisateurs sont requis"}), 400

        existing_chat = query_db(
            "SELECT * FROM chats WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)",
            (user1_id, user2_id, user2_id, user1_id),
            one=True
        )

        if existing_chat:
            return jsonify({"chat_id": existing_chat["id"]}), 200

        query_db("INSERT INTO chats (user1_id, user2_id) VALUES (?, ?)", (user1_id, user2_id), commit=True)
        chat_id = query_db("SELECT last_insert_rowid() AS id", one=True)["id"]

        return jsonify({"chat_id": chat_id}), 201
    except Exception as e:
        print(f"Erreur lors de la création du chat : {e}")
        return jsonify({"error": "Erreur interne du serveur"}), 500

@app.route('/chats/<int:user_id>', methods=['GET'])
def get_chats(user_id):
    # Vérifier que l'ID de l'utilisateur est valide et récupérer les chats associés
    chats = query_db("""
        SELECT * FROM chats
        WHERE user1_id = ? OR user2_id = ?
    """, (user_id, user_id))
    
    return jsonify([dict(chat) for chat in chats])



@app.route('/messages', methods=['GET'])
def get_messages():
    chat_id = request.args.get('chatId')

    if not chat_id:
        return jsonify({"error": "chatId is required"}), 400

    # Récupérer les messages du chat avec le nom de l'utilisateur qui a envoyé chaque message
    messages = query_db("""
    SELECT messages.id, messages.content, messages.timestamp, messages.sender_id, users.username
    FROM messages
    JOIN users ON messages.sender_id = users.id
    WHERE messages.chat_id = ?
    ORDER BY messages.timestamp
    """, (chat_id,))

    # Retourner les messages avec sender_id inclus
    return jsonify([{
        'id': message['id'],
        'content': message['content'],
        'timestamp': message['timestamp'],
        'username': message['username'],
        'sender_id': message['sender_id']  # Ajouter sender_id ici
    } for message in messages])


@app.route('/messages', methods=['POST'])
def send_message():
    data = request.json
    chat_id = data.get('chat_id')
    sender_id = data.get('sender_id')
    content = data.get('content')

    if not content:
        return jsonify({"error": "Le contenu du message est obligatoire"}), 400
    if not chat_id or not sender_id:
        return jsonify({"error": "Le chat_id et le sender_id sont requis"}), 400

    # Insérer le message dans la base de données
    query_db(
        "INSERT INTO messages (chat_id, sender_id, content) VALUES (?, ?, ?)",
        (chat_id, sender_id, content),
        commit=True
    )
    return jsonify({"message": "Message envoyé avec succès"}), 201


@app.route('/users/search', methods=['GET'])
def search_users():
    query = request.args.get('query', '').strip()

    if not query:
        return jsonify([])  # Retourne une liste vide si la requête est vide

    # Rechercher les utilisateurs par nom ou email
    users = query_db("""
        SELECT id, username, email
        FROM users
        WHERE username LIKE ? OR email LIKE ?
        LIMIT 10
    """, (f"%{query}%", f"%{query}%"))

    return jsonify([
        {"id": user["id"], "username": user["username"], "email": user["email"]}
        for user in users
    ])


@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    # Récupérer l'utilisateur par son ID
    user = query_db("SELECT id, username, email FROM users WHERE id = ?", (user_id,), one=True)

    if user:
        return jsonify({
            "id": user["id"],
            "username": user["username"],
            "email": user["email"]
        })
    else:
        return jsonify({"error": "Utilisateur non trouvé"}), 404


if __name__ == '__main__':
    app.run(debug=True)
