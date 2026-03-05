import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image

app = Flask(__name__)
app.secret_key = "secret_key"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# 🔥 added this line
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MODEL_PATH = "waste_classification_model.h5"
model = load_model(MODEL_PATH)


# ---------------- HELPER ----------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def classify_waste(img_path):
    try:
        img = image.load_img(img_path, target_size=(224, 224))
        x = image.img_to_array(img) / 255.0
        x = np.expand_dims(x, axis=0)

        pred = model.predict(x)[0]

        recyclable_prob = float(pred[0] * 100)
        non_recyclable_prob = 100 - recyclable_prob

        max_confidence = max(recyclable_prob, non_recyclable_prob)
        confidence_gap = abs(recyclable_prob - non_recyclable_prob)

        if max_confidence < 70 or confidence_gap < 20:
            return "Invalid Image", round(max_confidence, 2), "N/A"

        if recyclable_prob >= non_recyclable_prob:
            return "Recyclable", round(recyclable_prob, 2), "Blue Bin"
        else:
            return "Non-Recyclable", round(non_recyclable_prob, 2), "Red Bin"

    except:
        return "Invalid Image", 0, "N/A"


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    if "username" in session:
        return redirect("/upload")
    return render_template("welcome.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if os.path.exists("users/users.json"):
            with open("users/users.json", "r") as f:
                users = json.load(f)
        else:
            users = {}

        if username in users and check_password_hash(users[username], password):
            session["username"] = username
            return redirect("/upload")
        else:
            error = "Invalid username or password"

    return render_template("login.html", error=error)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        os.makedirs("users", exist_ok=True)
        users_file = "users/users.json"

        if os.path.exists(users_file):
            with open(users_file, "r") as f:
                users = json.load(f)
        else:
            users = {}

        if username in users:
            error = "Username already exists"
        else:
            users[username] = generate_password_hash(password)
            with open(users_file, "w") as f:
                json.dump(users, f, indent=4)

            session["username"] = username
            return redirect("/upload")

    return render_template("signup.html", error=error)


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/login")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "username" not in session:
        return redirect("/login")

    error = None
    image_path = None
    result = None
    percentage = None
    bin_name = None

    if request.method == "POST":
        file = request.files["image"]

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            user_folder = f"{UPLOAD_FOLDER}/{session['username']}"
            os.makedirs(user_folder, exist_ok=True)
            save_path = os.path.join(user_folder, filename)
            file.save(save_path)

            image_path = save_path.replace("\\", "/")
            result, percentage, bin_name = classify_waste(save_path)

            history_file = f"history/{session['username']}_history.json"
            os.makedirs("history", exist_ok=True)

            if os.path.exists(history_file):
                with open(history_file, "r") as f:
                    history_data = json.load(f)
            else:
                history_data = []

            history_data.append({
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "image": image_path,
                "result": result,
                "percentage": percentage,
                "bin": bin_name
            })

            with open(history_file, "w") as f:
                json.dump(history_data, f, indent=4)

        else:
            error = "Invalid file type"

    return render_template("upload.html",
                           error=error,
                           image_path=image_path,
                           result=result,
                           percentage=percentage,
                           bin=bin_name)


@app.route("/history")
def history():
    if "username" not in session:
        return redirect("/login")

    history_file = f"history/{session['username']}_history.json"

    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            data = json.load(f)
    else:
        data = []

    recyclable = sum(1 for i in data if i["result"] == "Recyclable")
    non_recyclable = sum(1 for i in data if i["result"] == "Non-Recyclable")

    return render_template("history.html",
                           history=data,
                           total=len(data),
                           recyclable=recyclable,
                           non_recyclable=non_recyclable)


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/login")

    history_file = f"history/{session['username']}_history.json"

    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            data = json.load(f)
    else:
        data = []

    total = len(data)
    recyclable = sum(1 for i in data if i["result"] == "Recyclable")
    non_recyclable = sum(1 for i in data if i["result"] == "Non-Recyclable")

    recyclable_percent = round((recyclable / total) * 100, 2) if total > 0 else 0
    recent = data[-5:][::-1]

    return render_template("dashboard.html",
                           total=total,
                           recyclable=recyclable,
                           non_recyclable=non_recyclable,
                           recyclable_percent=recyclable_percent,
                           recent=recent)


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
