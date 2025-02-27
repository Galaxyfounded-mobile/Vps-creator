from flask import Flask, request, render_template_string, jsonify
import os
import subprocess
import psutil
import logging
import time
import tempfile

app = Flask(__name__)
PORT = 6969

tmate_sessions = []

logging.basicConfig(level=logging.INFO)

def ensure_directories():
    try:
        os.makedirs("bot", exist_ok=True)
        os.makedirs("mate/sockets", exist_ok=True)
    except Exception as e:
        logging.error(f"Error creating directories: {e}")

ensure_directories()

template = """
<!DOCTYPE html>
<html>
<head>
    <title>Python Bot Hosting</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #1e1e1e; color: #ddd; text-align: center; }
        textarea { width: 90%; height: 200px; background: #2b2b2b; color: #0f0; border: 1px solid #444; padding: 10px; }
        button { margin: 10px; padding: 10px 20px; font-size: 16px; background: #007bff; color: white; border: none; border-radius: 5px; }
        button:hover { background: #0056b3; }
        pre { background: #111; color: #0f0; padding: 15px; text-align: left; overflow-x: auto; border-radius: 5px; }
        .container { width: 80%; margin: auto; padding: 20px; background: #2b2b2b; border-radius: 10px; box-shadow: 0px 0px 10px black; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Python Bot Hosting</h1>
        <form method="post">
            <textarea name="code">{{ code }}</textarea><br>
            <button type="submit">Run Code</button>
            <button type="submit" name="stop" value="1">Stop Execution</button>
        </form>
        <h2>Output:</h2>
        <pre>{{ output }}</pre>
        <br>
        <button onclick="startVPS()">Start VPS Session</button>
        <div id="vps-info"></div>
    </div>
    <script>
        function startVPS() {
            fetch('/vps')
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('vps-info').innerHTML = `<h1>Error</h1><p>${data.error}</p>`;
                    } else {
                        document.getElementById('vps-info').innerHTML = `<h1>Tmate Session Started</h1>
                        <p>SSH Access: ${data.ssh}</p>
                        <p>Web Access: ${data.web}</p>`;
                    }
                });
        }
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def home():
    output = ""
    code = ""
    if request.method == "POST":
        if "stop" in request.form:
            output = "Execution stopped."
        else:
            code = request.form.get("code", "")
            try:
                result = subprocess.run(["python3", "-c", code], capture_output=True, text=True, timeout=10)
                output = result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                output = "Execution timed out."
            except Exception as e:
                output = str(e)
    return render_template_string(template, code=code, output=output)

@app.route("/vps")
def vps():
    try:
        socket_path = os.path.join("mate/sockets", tempfile.mktemp(suffix=".sock"))
        command = f"tmate -S {socket_path} new-session -d"
        subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(1)
        ssh_info = subprocess.run(["tmate", "-S", socket_path, "display", "-p", "#{tmate_ssh}"], capture_output=True, text=True)
        web_info = subprocess.run(["tmate", "-S", socket_path, "display", "-p", "#{tmate_web}"], capture_output=True, text=True)
        if ssh_info.returncode != 0 or not ssh_info.stdout.strip():
            return jsonify({"error": "Could not get SSH info."})
        if web_info.returncode != 0 or not web_info.stdout.strip():
            return jsonify({"error": "Could not get Web info."})
        session_data = {"ssh": ssh_info.stdout.strip(), "web": web_info.stdout.strip(), "socket": socket_path}
        tmate_sessions.append(session_data)
        return jsonify(session_data)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/adminlogs")
def adminlogs():
    session_list = "".join(f"<li>{s['ssh']} - {s['web']}</li>" for s in tmate_sessions)
    return f"""
    <html>
    <body>
        <h1>Active Tmate Sessions</h1>
        <ul>{session_list}</ul>
        <a href='/adminhome'>Manage Sessions</a>
    </body>
    </html>
    """

@app.route("/adminhome", methods=["GET", "POST"])
def adminhome():
    if request.method == "POST":
        data = request.get_json()
        session_ssh = data.get("ssh")
        global tmate_sessions
        tmate_sessions = [s for s in tmate_sessions if s["ssh"] != session_ssh]
        return "Session deleted successfully"
    
    session_buttons = "".join(f"<li>{s['ssh']} <button onclick=\"deleteSession('{s['ssh']}')\">Delete</button></li>" for s in tmate_sessions)
    
    return f"""
    <html>
    <body>
        <h1>Manage Tmate Sessions</h1>
        <ul>{session_buttons}</ul>
        <script>
            function deleteSession(ssh) {{
                fetch('/adminhome', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ 'ssh': ssh }})
                }}).then(() => location.reload());
            }}
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
