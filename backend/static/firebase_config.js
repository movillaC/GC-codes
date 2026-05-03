import { initializeApp } from "https://www.gstatic.com/firebasejs/11.6.0/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/11.6.0/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/11.6.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyClZbRCX0Uf6UFr_Nvv7p6GG0nFnm8ezdU",
  authDomain: "gcsw-cca5d.firebaseapp.com",
  projectId: "gcsw-cca5d",
  storageBucket: "gcsw-cca5d.firebasestorage.app",
  messagingSenderId: "1092609196334",
  appId: "1:1092609196334:web:d39548bb55410c8eee3abf"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

export { auth, db };
