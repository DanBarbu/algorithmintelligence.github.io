import { useState } from "react";
import Login from "./components/Login";
import CesiumMap from "./components/CesiumMap";

export default function App(): JSX.Element {
  const [authed, setAuthed] = useState(false);

  return authed ? <CesiumMap /> : <Login onSuccess={() => setAuthed(true)} />;
}
