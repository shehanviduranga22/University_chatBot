from flask import Flask, request, jsonify
from flask_cors import CORS

from rag_engine import UniversityRAG
from account_service import authenticate_account, create_account

from faster_whisper import WhisperModel

import os
import uuid


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

CORS(app)


# =========================================================
# STUDENT ACCOUNT API
# =========================================================

@app.post("/api/auth/register")
def register_student():

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400

    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    try:
        return jsonify({"account": create_account(name, email, password)}), 201
    except Exception as error:
        if error.__class__.__name__ == "DuplicateKeyError":
            return jsonify({"error": "An account with that email already exists."}), 409
        if isinstance(error, RuntimeError):
            return jsonify({"error": str(error)}), 503
        print("ACCOUNT REGISTRATION ERROR:", str(error))
        return jsonify({"error": "Could not create the student account."}), 500


@app.post("/api/auth/login")
def login_student():

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    try:
        account = authenticate_account(email, password)
        if account is None:
            return jsonify({"error": "Invalid student email or password."}), 401
        return jsonify({"account": account})
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except Exception as error:
        print("ACCOUNT LOGIN ERROR:", str(error))
        return jsonify({"error": "Could not log in at this time."}), 500


# =========================================================
# UNIVERSITY RAG
# =========================================================

print("=" * 60)
print("Loading University RAG...")
print("=" * 60)

rag = UniversityRAG()

print("University RAG loaded successfully.")


# =========================================================
# WHISPER SPEECH-TO-TEXT
# =========================================================

print("=" * 60)
print("Loading Faster-Whisper...")
print("=" * 60)


# ---------------------------------------------------------
# Whisper model
#
# base = better accuracy
# tiny = faster / less RAM
# ---------------------------------------------------------

WHISPER_MODEL = os.getenv(
    "WHISPER_MODEL",
    "base"
)


try:

    whisper = WhisperModel(
        WHISPER_MODEL,

        # CPU is suitable for your setup
        device="cpu",

        # Reduces RAM usage
        compute_type="int8"
    )

    print(
        f"Whisper model loaded: {WHISPER_MODEL}"
    )

except Exception as e:

    print(
        "ERROR: Could not load Whisper model."
    )

    print(str(e))

    whisper = None


# =========================================================
# TEMP AUDIO DIRECTORY
# =========================================================

TEMP_AUDIO_DIR = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)
    ),
    "temp_audio"
)


os.makedirs(
    TEMP_AUDIO_DIR,
    exist_ok=True
)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/api/health")
def health():

    try:

        return jsonify({
            "status": "ok",

            "model": rag.model,

            "documents":
                rag.collection.count(),

            "whisper":
                whisper is not None,

            "whisper_model":
                WHISPER_MODEL
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "details": str(e)
        }), 500


# =========================================================
# CHAT
# =========================================================

@app.post("/api/chat")
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    question = (
        data.get("message") or ""
    ).strip()

    history = (
        data.get("history") or []
    )


    # -----------------------------------------------------
    # VALIDATE
    # -----------------------------------------------------

    if not question:

        return jsonify({
            "error":
                "Message is required"
        }), 400


    # -----------------------------------------------------
    # RAG ANSWER
    # -----------------------------------------------------

    try:

        result = rag.answer(
            question,
            history
        )

        return jsonify(result)

    except Exception as e:

        print(
            "CHATBOT ERROR:",
            str(e)
        )

        return jsonify({

            "error":
                "Chatbot error",

            "details":
                str(e)

        }), 500


# =========================================================
# VOICE -> TEXT
# =========================================================

@app.post("/api/transcribe")
def transcribe_audio():

    temp_file = None

    try:

        # -------------------------------------------------
        # CHECK WHISPER
        # -------------------------------------------------

        if whisper is None:

            return jsonify({

                "error":
                    "Whisper model is not loaded."

            }), 500


        # -------------------------------------------------
        # CHECK AUDIO
        # -------------------------------------------------

        if "audio" not in request.files:

            return jsonify({

                "error":
                    "No audio file received."

            }), 400


        audio = request.files["audio"]


        if not audio.filename:

            return jsonify({

                "error":
                    "Audio filename is empty."

            }), 400


        # -------------------------------------------------
        # CREATE UNIQUE FILE
        # -------------------------------------------------

        filename = (
            f"{uuid.uuid4().hex}.webm"
        )


        temp_file = os.path.join(
            TEMP_AUDIO_DIR,
            filename
        )


        # -------------------------------------------------
        # SAVE AUDIO
        # -------------------------------------------------

        audio.save(temp_file)


        print("=" * 60)

        print(
            "🎤 Audio received:"
        )

        print(temp_file)

        print("=" * 60)


        # -------------------------------------------------
        # WHISPER TRANSCRIPTION
        # -------------------------------------------------

        segments, info = whisper.transcribe(

            temp_file,

            # Better recognition
            beam_size=5,

            # Ignore long silence
            vad_filter=True,

            # Prevent hallucinations
            condition_on_previous_text=False
        )


        # -------------------------------------------------
        # COLLECT TRANSCRIPT
        # -------------------------------------------------

        text_parts = []


        for segment in segments:

            text = (
                segment.text or ""
            ).strip()


            if text:

                text_parts.append(
                    text
                )


        transcript = " ".join(
            text_parts
        ).strip()


        # -------------------------------------------------
        # LOG
        # -------------------------------------------------

        print(
            "📝 Transcription:"
        )

        print(transcript)


        print(
            "🌐 Detected language:",
            info.language
        )


        print(
            "📊 Language probability:",
            info.language_probability
        )


        # -------------------------------------------------
        # DELETE AUDIO
        # -------------------------------------------------

        try:

            os.remove(
                temp_file
            )

            temp_file = None

        except Exception as delete_error:

            print(
                "Could not delete temp file:",
                delete_error
            )


        # -------------------------------------------------
        # NO SPEECH
        # -------------------------------------------------

        if not transcript:

            return jsonify({

                "text": "",

                "language":
                    info.language,

                "message":
                    "No speech detected."

            }), 200


        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return jsonify({

            "text":
                transcript,

            "language":
                info.language,

            "language_probability":
                info.language_probability

        })


    except Exception as e:

        print("=" * 60)

        print(
            "❌ TRANSCRIPTION ERROR"
        )

        print(str(e))

        print("=" * 60)


        # -------------------------------------------------
        # DELETE TEMP FILE
        # -------------------------------------------------

        if temp_file:

            try:

                if os.path.exists(
                    temp_file
                ):

                    os.remove(
                        temp_file
                    )

            except Exception:

                pass


        return jsonify({

            "error":
                "Speech transcription failed.",

            "details":
                str(e)

        }), 500


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    host = os.getenv(
        "FLASK_HOST",
        "127.0.0.1"
    )


    port = int(
        os.getenv(
            "FLASK_PORT",
            "5000"
        )
    )


    print("=" * 60)

    print(
        "University Chatbot Backend"
    )

    print(
        f"Server: http://{host}:{port}"
    )

    print(
        f"Whisper: {WHISPER_MODEL}"
    )

    print("=" * 60)


    app.run(

        host=host,

        port=port,

        debug=True
    )