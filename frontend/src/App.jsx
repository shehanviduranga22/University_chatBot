import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import {
  createStudentAccount,
  loginStudent,
} from "./services/accountService";
import {
  Bot,
  Mic,
  MicOff,
  Send,
  Copy,
  Volume2,
  StopCircle,
  Trash2,
  ThumbsUp,
  ThumbsDown,
  ExternalLink,
  FileSearch,
  Sparkles,
  Bell,
  CalendarDays,
  ArrowUpRight,
  UserRound,
  LockKeyhole,
  Mail,
  MapPinned,
  X,
  LogOut,
} from "lucide-react";
import assistantIcon from "./assets/logo.png";
import userIcon from "./assets/you.png";
import sabraIcon from "./assets/sabra.png";
import botIcon from "./assets/bot.png";

const API = "http://127.0.0.1:5000";

const welcome = {
  role: "assistant",
  content:
    "Hello! 👋 I’m your University AI Assistant. Ask me about admissions, courses, examinations, student services, hostels, regulations and other university information.",
  sources: [],
};

export default function App() {
  const [messages, setMessages] = useState([welcome]);

  const [input, setInput] = useState("");

  const [loading, setLoading] = useState(false);

  const [authOpen, setAuthOpen] = useState(false);

  const [authMode, setAuthMode] = useState("login");

  const [student, setStudent] = useState(null);

  const [authForm, setAuthForm] = useState({
    name: "",
    email: "",
    password: "",
  });

  const [authError, setAuthError] = useState("");

  const [authLoading, setAuthLoading] = useState(false);

  const [accountOpen, setAccountOpen] = useState(false);

  const [campusMapOpen, setCampusMapOpen] = useState(false);

  const [openSources, setOpenSources] = useState({});

  const campusCenter = { lat: 6.7149, lng: 80.7863 };

  const universityNotices = [
    {
      title: "Victim Support Services - SUSL",
      date: "2026-08-21",
    },
    {
      title: "Calling Applications - Rented Student Hostels - Closing Date 11.09.2026",
      date: "2026-08-21",
    },
    {
      title: "Issuing of Admission Cards Faculty of Applied Science, Department of PST/NR",
      date: "2026-07-31",
    },
  ];

  const [speakingMessage, setSpeakingMessage] = useState(null);

  const [selectedActions, setSelectedActions] = useState({});

  // Voice recording state
  const [listening, setListening] = useState(false);

  // Whisper transcription state
  const [transcribing, setTranscribing] =
    useState(false);

  const [voiceError, setVoiceError] =
    useState("");

  // MediaRecorder
  const mediaRecorderRef =
    useRef(null);

  // Audio chunks
  const audioChunksRef =
    useRef([]);

  const bottomRef =
    useRef(null);


  // =========================================================
  // AUTO SCROLL
  // =========================================================

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);


  // =========================================================
  // SEND MESSAGE
  // =========================================================

  const sendMessage = async (text = input) => {
    const question = text.trim();

    if (!question || loading) return;

    const history = messages
      .slice(-6)
      .map((m) => ({
        role: m.role,
        content: m.content,
      }));

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: question,
      },
    ]);

    setInput("");

    setLoading(true);

    try {
      const res = await fetch(
        `${API}/api/chat`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            message: question,
            history,
          }),
        }
      );

      const data =
        await res.json();

      if (!res.ok) {
        throw new Error(
          data.details ||
            data.error ||
            "Request failed"
        );
      }

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",

          content:
            data.answer ||
            "Sorry, I could not generate an answer.",

          sources:
            data.sources || [],

          confidence:
            data.confidence,
        },
      ]);

    } catch (err) {
      console.error(
        "CHAT ERROR:",
        err
      );

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",

          content:
            "Sorry, I couldn't connect to the university chatbot server. Please make sure the Flask backend and Ollama are running.",

          sources: [],
        },
      ]);

    } finally {
      setLoading(false);
    }
  };


  // =========================================================
  // START / STOP VOICE RECORDING
  //
  // React Microphone
  //        ↓
  // MediaRecorder
  //        ↓
  // Audio Blob
  //        ↓
  // Flask /api/transcribe
  //        ↓
  // Faster-Whisper
  //        ↓
  // Text
  // =========================================================

  const startVoice = async () => {

    setVoiceError("");

    // -------------------------------------------------------
    // IF ALREADY RECORDING -> STOP
    // -------------------------------------------------------

    if (listening) {

      console.log(
        "🎤 Stopping recording..."
      );

      if (
        mediaRecorderRef.current
      ) {
        try {
          mediaRecorderRef.current.stop();
        } catch (error) {
          console.error(
            "Stop recording error:",
            error
          );
        }
      }

      return;
    }


    // -------------------------------------------------------
    // CHECK BROWSER MEDIA SUPPORT
    // -------------------------------------------------------

    if (
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia
    ) {

      setVoiceError(
        "Microphone is not supported by this browser."
      );

      return;
    }


    // -------------------------------------------------------
    // REQUEST MICROPHONE
    // -------------------------------------------------------

    try {

      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

      console.log(
        "🎤 Microphone permission granted"
      );


      // -----------------------------------------------------
      // RESET AUDIO CHUNKS
      // -----------------------------------------------------

      audioChunksRef.current = [];


      // -----------------------------------------------------
      // DETERMINE AUDIO FORMAT
      // -----------------------------------------------------

      let mimeType =
        "audio/webm";


      if (
        MediaRecorder.isTypeSupported(
          "audio/webm;codecs=opus"
        )
      ) {
        mimeType =
          "audio/webm;codecs=opus";
      }


      // -----------------------------------------------------
      // CREATE MEDIA RECORDER
      // -----------------------------------------------------

      const recorder =
        new MediaRecorder(
          stream,
          {
            mimeType,
          }
        );


      mediaRecorderRef.current =
        recorder;


      // -----------------------------------------------------
      // AUDIO DATA
      // -----------------------------------------------------

      recorder.ondataavailable =
        (event) => {

          if (
            event.data &&
            event.data.size > 0
          ) {

            audioChunksRef.current.push(
              event.data
            );

          }
        };


      // -----------------------------------------------------
      // RECORDING START
      // -----------------------------------------------------

      recorder.onstart = () => {

        console.log(
          "🎤 Recording started"
        );

        setListening(true);

        setTranscribing(false);

        setVoiceError("");
      };


      // -----------------------------------------------------
      // RECORDING STOP
      // -----------------------------------------------------

      recorder.onstop = async () => {

        console.log(
          "🎤 Recording stopped"
        );


        setListening(false);


        // Stop microphone
        stream
          .getTracks()
          .forEach((track) => {
            track.stop();
          });


        // ---------------------------------------------------
        // CREATE AUDIO BLOB
        // ---------------------------------------------------

        const audioBlob =
          new Blob(
            audioChunksRef.current,
            {
              type: mimeType,
            }
          );


        console.log(
          "🎵 Audio size:",
          audioBlob.size
        );


        // ---------------------------------------------------
        // CHECK AUDIO
        // ---------------------------------------------------

        if (
          audioBlob.size === 0
        ) {

          setVoiceError(
            "No audio was recorded. Please try again."
          );

          return;
        }


        // ---------------------------------------------------
        // SEND TO WHISPER
        // ---------------------------------------------------

        await transcribeVoice(
          audioBlob
        );

      };


      // -----------------------------------------------------
      // RECORDER ERROR
      // -----------------------------------------------------

      recorder.onerror = (event) => {

        console.error(
          "🎤 Recorder error:",
          event
        );

        setListening(false);

        setVoiceError(
          "Microphone recording failed."
        );

      };


      // -----------------------------------------------------
      // START RECORDING
      // -----------------------------------------------------

      recorder.start();

      console.log(
        "🎤 MediaRecorder started"
      );

    } catch (error) {

      console.error(
        "❌ Microphone error:",
        error
      );

      setListening(false);


      if (
        error.name ===
        "NotAllowedError"
      ) {

        setVoiceError(
          "Microphone permission was denied. Please allow microphone access in Chrome."
        );

      } else if (
        error.name ===
        "NotFoundError"
      ) {

        setVoiceError(
          "No microphone was found. Please connect a microphone."
        );

      } else if (
        error.name ===
        "NotReadableError"
      ) {

        setVoiceError(
          "Microphone is being used by another application."
        );

      } else {

        setVoiceError(
          "Could not access microphone."
        );

      }
    }
  };


  // =========================================================
  // SEND AUDIO TO FLASK
  // =========================================================

  const transcribeVoice =
    async (audioBlob) => {

      setTranscribing(true);

      setVoiceError("");


      try {

        console.log(
          "📤 Sending audio to Whisper..."
        );


        // ---------------------------------------------------
        // FORM DATA
        // ---------------------------------------------------

        const formData =
          new FormData();


        formData.append(
          "audio",
          audioBlob,
          "voice.webm"
        );


        // ---------------------------------------------------
        // API REQUEST
        // ---------------------------------------------------

        const response =
          await fetch(
            `${API}/api/transcribe`,
            {
              method: "POST",
              body: formData,
            }
          );


        const data =
          await response.json();


        console.log(
          "📝 Whisper response:",
          data
        );


        // ---------------------------------------------------
        // ERROR
        // ---------------------------------------------------

        if (!response.ok) {

          throw new Error(
            data.details ||
              data.error ||
              "Transcription failed."
          );
        }


        // ---------------------------------------------------
        // GET TEXT
        // ---------------------------------------------------

        const text =
          (data.text || "").trim();


        console.log(
          "🎤 Converted text:",
          text
        );


        // ---------------------------------------------------
        // SUCCESS
        // ---------------------------------------------------

        if (text) {

          setInput(text);

          setVoiceError("");

          console.log(
            "✅ Voice converted to text successfully"
          );

        } else {

          setVoiceError(
            "No speech was detected. Please speak again."
          );

        }

      } catch (error) {

        console.error(
          "❌ TRANSCRIPTION ERROR:",
          error
        );


        setVoiceError(
          error.message ||
            "Could not transcribe your voice."
        );

      } finally {

        setTranscribing(false);

      }
    };


  // =========================================================
  // TEXT TO SPEECH
  // =========================================================

  const speak = (text, messageIndex) => {

    if (speakingMessage === messageIndex) {
      window.speechSynthesis?.cancel();
      setSpeakingMessage(null);
      return;
    }

    if (
      !("speechSynthesis" in window)
    ) {

      alert(
        "Voice output is not supported by this browser."
      );

      return;
    }


    window.speechSynthesis.cancel();


    const utterance =
      new SpeechSynthesisUtterance(
        text
      );

    utterance.onend = () => {
      setSpeakingMessage(null);
    };

    utterance.onerror = () => {
      setSpeakingMessage(null);
    };


    utterance.rate = 0.95;

    utterance.pitch = 1;

    utterance.volume = 1;


    setSpeakingMessage(messageIndex);
    window.speechSynthesis.speak(utterance);
  };


  // =========================================================
  // COPY TEXT
  // =========================================================

  const copyText = async (text) => {

    try {

      await navigator.clipboard.writeText(
        text
      );

      console.log(
        "Text copied"
      );

    } catch (error) {

      console.error(
        "Copy error:",
        error
      );
    }
  };

  const toggleAction = (messageIndex, action) => {
    setSelectedActions((previous) => ({
      ...previous,
      [`${messageIndex}-${action}`]: !previous[`${messageIndex}-${action}`],
    }));
  };

  const toggleSources = (messageIndex) => {
    setOpenSources((previous) => ({
      ...previous,
      [messageIndex]: !previous[messageIndex],
    }));
  };


  // =========================================================
  // CLEAR CHAT
  // =========================================================

  const clearChat = () => {

    setMessages([welcome]);

    setOpenSources({});

    setSelectedActions({});

    setInput("");

    setVoiceError("");

    setTranscribing(false);


    // Stop TTS
    window.speechSynthesis?.cancel();

    setSpeakingMessage(null);


    // Stop microphone
    if (
      mediaRecorderRef.current
    ) {

      try {

        mediaRecorderRef.current.stop();

      } catch (error) {

        console.log(
          "Recorder stop:",
          error
        );

      }

      mediaRecorderRef.current =
        null;
    }


    setListening(false);

    audioChunksRef.current = [];
  };


  // =========================================================
  // SUGGESTIONS
  // =========================================================

  const suggestions = [
    "What degree programmes are available?",
    "How can I apply for hostel accommodation?",
    "What are the admission requirements?",
    "Where can I find examination information?",
  ];

  const openAuth = (mode = "login") => {
    setAuthMode(mode);
    setAuthError("");
    setAuthOpen(true);
  };

  const handleAuthSubmit = async (event) => {
    event.preventDefault();
    const email = authForm.email.trim().toLowerCase();

    if (!email || !authForm.password.trim() || (authMode === "signup" && !authForm.name.trim())) {
      setAuthError("Please complete all required fields.");
      return;
    }

    setAuthLoading(true);
    setAuthError("");

    try {
      const account = authMode === "signup"
        ? await createStudentAccount({ name: authForm.name.trim(), email, password: authForm.password })
        : await loginStudent({ email, password: authForm.password });

      setAuthForm({ name: "", email: "", password: "" });
      if (authMode === "signup") {
        setAuthMode("login");
        setAuthError("Account created. Please log in with your new account.");
      } else {
        setStudent(account);
        setAuthOpen(false);
      }
    } catch (error) {
      setAuthError(error.message || "Could not connect to the account service.");
    } finally {
      setAuthLoading(false);
    }
  };

  const openAccount = () => {
    if (student) setAccountOpen(true);
    else openAuth("login");
  };


  // =========================================================
  // UI
  // =========================================================

  return (

    <div className="app">


      {/* =====================================================
          SIDEBAR
      ===================================================== */}

      <aside className="sidebar">


        {/* BRAND */}

        <div className="brand">

          <img
            className="brand-image"
            src={sabraIcon}
            alt="Sabaragamuwa University logo"
          />


          <div>

            <h1>
              Sabaragamuwa University of Sri Lanka
            </h1>

            <p>
              Knowledge Assistant
            </p>

          </div>

        </div>


        {/* NEW CHAT */}

        <button
          className="new-chat"
          onClick={clearChat}
        >

          <Sparkles size={17} />

          New conversation

        </button>


        {/* CAPABILITIES */}

        <div className="side-section">

          <div className="side-label">
            Capabilities
          </div>


          <div className="capability">
            📚 University documents
          </div>


          <div className="capability">
            🌐 Official website data
          </div>


          <div className="capability">
            🎤 Voice input
          </div>


          <div className="capability">
            🔊 Voice answers
          </div>


          <div className="capability">
            🔎 Source references
          </div>

        </div>


        {/* STATUS */}

        <button className="student-login" onClick={() => openAuth()}>
          <UserRound size={16} />
          {student ? `Hi, ${student.name}` : "Student login"}
        </button>

        <button
          className="student-map-button"
          type="button"
          onClick={() => setCampusMapOpen(true)}
          aria-label="Open Sabaragamuwa University campus map"
        >
          <MapPinned size={15} />
          Campus map
        </button>

        <div className="side-footer">

          <span className="status-dot"></span>

          Local AI system online

        </div>

      </aside>

      <aside className="notice-panel" aria-labelledby="notice-title">
        <div className="notice-heading">
          <Bell size={17} />
          <span>Special notice</span>
        </div>
        <div className="notice-accent" />
        <h2 id="notice-title">Latest university notices</h2>
        {universityNotices.map((notice) => (
          <article key={notice.title} className="notice-item">
            <h2>{notice.title}</h2>
            <p className="notice-date">
              <CalendarDays size={15} />
              {notice.date}
            </p>
          </article>
        ))}
        <a className="notice-link" href="https://www.sab.ac.lk/notices" target="_blank" rel="noopener noreferrer">
          View all notices <ArrowUpRight size={15} />
        </a>
      </aside>



      {/* =====================================================
          MAIN
      ===================================================== */}

      <main className="main">


        {/* TOP BAR */}

        <header className="topbar">

          <div>

            <div className="online">

              <span className="status-dot"></span>

              University Assistant

            </div>


            <span className="subtitle">

              Official knowledge-base powered chatbot

            </span>

          </div>


          <div className="topbar-actions">
            <button
              className="icon-btn"
              onClick={clearChat}
              title="Clear chat"
            >

              <Trash2 size={19} />

            </button>

            <button
              className="icon-btn account-icon"
              onClick={openAccount}
              title={student ? "View account details" : "Student login"}
              aria-label={student ? "View account details" : "Student login"}
            >
              <UserRound size={19} />
            </button>
          </div>

        </header>



        {/* ===================================================
            CHAT
        =================================================== */}

        <section className="chat">


          {/* HERO */}

          {messages.length === 1 && (

            <div className="hero">

              <img
                className="chatbot-image"
                src={botIcon}
                alt="Friendly university chatbot"
              />


              <h2>
                How can I help you today?
              </h2>


              <p>

                Ask questions about the university
                using natural language or your voice.

              </p>


              <div className="suggestions">

                {suggestions.map(
                  (s) => (

                    <button
                      key={s}
                      onClick={() =>
                        sendMessage(s)
                      }
                    >

                      {s}

                    </button>

                  )
                )}

              </div>

            </div>

          )}



          {/* =================================================
              MESSAGES
          ================================================= */}

          {messages.map(
            (m, i) => (

              <div
                className={`message-row ${m.role}`}
                key={i}
              >


                {/* AVATAR */}

                <div className="avatar">

                  {m.role ===
                  "assistant"
                    ? <img src={assistantIcon} alt="Uni Assistant" />
                    : <img src={userIcon} alt="You" />}

                </div>


                {/* CONTENT */}

                <div className="message-content">

                  <div className="message-bubble">

                    <ReactMarkdown remarkPlugins={[remarkGfm]}>

                      {m.content}

                    </ReactMarkdown>


                    {/* ASSISTANT ACTIONS */}

                    {m.role ===
                      "assistant" && (

                      <div className="message-actions">


                        {/* COPY */}

                        <button
                          className={selectedActions[`${i}-copy`] ? "active" : ""}
                          onClick={() => {
                            copyText(m.content);
                            toggleAction(i, "copy");
                          }}
                          title="Copy"
                          aria-label="Copy response"
                        >

                          <Copy size={15} />

                        </button>


                        {/* SPEAK */}

                        <button
                          onClick={() =>
                            speak(
                              m.content,
                              i
                            )
                          }
                          title={speakingMessage === i ? "Stop" : "Listen"}
                          aria-label={speakingMessage === i ? "Stop listening" : "Listen to response"}
                          className={speakingMessage === i ? "active" : ""}
                        >

                          {speakingMessage === i ? (
                            <StopCircle size={15} />
                          ) : (
                            <Volume2 size={15} />
                          )}

                        </button>


                        {/* LIKE */}

                        <button
                          className={selectedActions[`${i}-helpful`] ? "active" : ""}
                          onClick={() => toggleAction(i, "helpful")}
                          title="Helpful"
                          aria-label="Helpful"
                        >

                          <ThumbsUp
                            size={15}
                          />

                        </button>


                        {/* DISLIKE */}

                        <button
                          className={selectedActions[`${i}-not-helpful`] ? "active" : ""}
                          onClick={() => toggleAction(i, "not-helpful")}
                          title="Not helpful"
                          aria-label="Not helpful"
                        >

                          <ThumbsDown
                            size={15}
                          />

                        </button>

                        {m.sources?.length > 0 && (
                          <button
                            className={openSources[i] ? "active" : ""}
                            onClick={() => toggleSources(i)}
                            title={openSources[i] ? "Hide sources" : "Show sources"}
                            aria-label={openSources[i] ? "Hide sources" : "Show sources"}
                            aria-expanded={openSources[i] || false}
                          >
                            <FileSearch size={15} />
                          </button>
                        )}

                      </div>

                    )}

                  </div>



                  {/* =================================================
                      SOURCES
                  ================================================= */}

                  {m.sources?.length > 0 && openSources[i] && (

                    <div className="sources">

                      <div className="source-title">

                        Sources

                      </div>


                      {m.sources.map(
                        (s, idx) => (

                          <div
                            className="source-card"
                            key={idx}
                          >

                            <div>

                              <strong>

                                {s.title ||
                                  s.source}

                              </strong>


                              <span>

                                {s.source}

                                {s.page
                                  ? ` · Page ${s.page}`
                                  : ""}

                              </span>

                            </div>


                            {s.url && (

                              <a
                                href={s.url}
                                target="_blank"
                                rel="noreferrer"
                              >

                                <ExternalLink
                                  size={15}
                                />

                              </a>

                            )}

                          </div>

                        )
                      )}

                    </div>

                  )}

                </div>

              </div>

            )
          )}



          {/* =================================================
              TYPING
          ================================================= */}

          {loading && (

            <div className="message-row assistant">

              <div className="avatar">

                <img src={assistantIcon} alt="Uni Assistant" />

              </div>


              <div className="message-bubble typing">

                <span></span>

                <span></span>

                <span></span>

              </div>

            </div>

          )}


          <div ref={bottomRef} />

        </section>



        {/* ===================================================
            COMPOSER
        =================================================== */}

        <div className="composer-wrap">


          <div className="composer">


            {/* =================================================
                MICROPHONE
            ================================================= */}

            <button
              className={`voice-btn ${
                listening
                  ? "active"
                  : ""
              }`}
              onClick={
                startVoice
              }
              disabled={
                transcribing
              }
              title={
                transcribing
                  ? "Transcribing..."
                  : listening
                  ? "Stop recording"
                  : "Start voice input"
              }
            >

              {listening ? (

                <MicOff size={21} />

              ) : (

                <Mic size={21} />

              )}

            </button>



            {/* =================================================
                TEXT INPUT
            ================================================= */}

            <textarea
              value={input}
              onChange={(e) =>
                setInput(
                  e.target.value
                )
              }
              onKeyDown={(e) => {

                if (
                  e.key ===
                    "Enter" &&
                  !e.shiftKey
                ) {

                  e.preventDefault();

                  sendMessage();

                }

              }}
              placeholder={
                listening
                  ? "🎤 Recording... click microphone to stop"
                  : transcribing
                  ? "⏳ Transcribing your voice..."
                  : "Ask a question about the university..."
              }
              rows="1"
            />



            {/* =================================================
                SEND
            ================================================= */}

            <button
              className="send-btn"
              onClick={() =>
                sendMessage()
              }
              disabled={
                !input.trim() ||
                loading ||
                transcribing
              }
              title="Send"
            >

              <Send size={20} />

            </button>

          </div>



          {/* =================================================
              VOICE STATUS / ERROR
          ================================================= */}

          {listening && (

            <div
              style={{
                color: "#3b82f6",
                fontSize: "13px",
                marginTop: "8px",
                textAlign: "center",
              }}
            >

              🎤 Recording... speak now, then
              click the microphone again to stop.

            </div>

          )}


          {transcribing && (

            <div
              style={{
                color: "#3b82f6",
                fontSize: "13px",
                marginTop: "8px",
                textAlign: "center",
              }}
            >

              ⏳ Transcribing your voice...

            </div>

          )}


          {voiceError && (

            <div
              style={{
                color: "#ef4444",
                fontSize: "13px",
                marginTop: "8px",
                textAlign: "center",
              }}
            >

              🎤 {voiceError}

            </div>

          )}



          {/* DISCLAIMER */}

          <div className="disclaimer">

            AI answers are generated from
            the university knowledge base.
            Always verify critical information
            with the official university office.

          </div>

        </div>

      </main>

      {campusMapOpen && (
        <div className="campus-map-backdrop" role="presentation" onMouseDown={() => setCampusMapOpen(false)}>
          <div className="campus-map-modal" role="dialog" aria-modal="true" aria-labelledby="campus-map-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="campus-map-close" type="button" onClick={() => setCampusMapOpen(false)} aria-label="Close campus map">
              <X size={18} />
            </button>

            <div className="campus-map-header">
              <div className="campus-map-icon"><MapPinned size={20} /></div>
              <div>
                <h2 id="campus-map-title">University Map</h2>
                <p>Belihuloya, Sri Lanka</p>
              </div>
            </div>

            <div className="campus-map-container">
              <MapContainer
                center={[campusCenter.lat, campusCenter.lng]}
                zoom={16}
                minZoom={12}
                maxZoom={18}
                zoomSnap={0.25}
                scrollWheelZoom={true}
                className="campus-map"
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  maxZoom={19}
                />
                <CircleMarker center={[campusCenter.lat, campusCenter.lng]} radius={12} pathOptions={{ color: "#176fe5", fillColor: "#176fe5", fillOpacity: 0.9 }}>
                  <Popup>
                    Sabaragamuwa University of Sri Lanka
                  </Popup>
                </CircleMarker>
              </MapContainer>
            </div>
          </div>
        </div>
      )}

      {authOpen && (
        <div className="auth-backdrop" role="presentation" onMouseDown={() => setAuthOpen(false)}>
          <section className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="auth-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="auth-close" type="button" onClick={() => setAuthOpen(false)} aria-label="Close student login">
              <X size={18} />
            </button>
            <div className="auth-icon"><UserRound size={22} /></div>
            <h2 id="auth-title">{authMode === "login" ? "Student login" : "Create student account"}</h2>
            <p className="auth-subtitle">Access your university student services.</p>

            <form onSubmit={handleAuthSubmit}>
              {authMode === "signup" && (
                <label className="auth-field">
                  Full name
                  <span><UserRound size={16} /><input value={authForm.name} onChange={(event) => setAuthForm({ ...authForm, name: event.target.value })} /></span>
                </label>
              )}
              <label className="auth-field">
                University email
                <span><Mail size={16} /><input type="email" value={authForm.email} onChange={(event) => setAuthForm({ ...authForm, email: event.target.value })} /></span>
              </label>
              <label className="auth-field">
                Password
                <span><LockKeyhole size={16} /><input type="password" value={authForm.password} onChange={(event) => setAuthForm({ ...authForm, password: event.target.value })} /></span>
              </label>
              {authError && <p className="auth-error">{authError}</p>}
              <button className="auth-submit" type="submit" disabled={authLoading}>
                {authLoading ? "Please wait..." : authMode === "login" ? "Log in" : "Create account"}
              </button>
            </form>

            <button className="auth-switch" type="button" onClick={() => { setAuthMode(authMode === "login" ? "signup" : "login"); setAuthError(""); }}>
              {authMode === "login" ? "New student? Create an account" : "Already have an account? Log in"}
            </button>
          </section>
        </div>
      )}

      {accountOpen && student && (
        <div className="auth-backdrop" role="presentation" onMouseDown={() => setAccountOpen(false)}>
          <section className="auth-modal" role="dialog" aria-modal="true" aria-labelledby="account-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="auth-close" type="button" onClick={() => setAccountOpen(false)} aria-label="Close account details"><X size={18} /></button>
            <div className="auth-icon"><UserRound size={22} /></div>
            <h2 id="account-title">Student account</h2>
            <p className="auth-subtitle">You are currently logged in.</p>
            <dl className="account-details">
              <div><dt>Name</dt><dd>{student.name}</dd></div>
              <div><dt>Email</dt><dd>{student.email}</dd></div>
            </dl>
            <button className="auth-submit logout-button" type="button" onClick={() => { setStudent(null); setAccountOpen(false); }}><LogOut size={16} /> Log out</button>
          </section>
        </div>
      )}

    </div>
  );
}