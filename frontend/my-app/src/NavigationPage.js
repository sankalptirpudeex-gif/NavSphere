import React, { useState, useEffect, useRef } from "react";
import { GoogleMap, LoadScript, DirectionsRenderer, Autocomplete, Marker } from "@react-google-maps/api";

const GOOGLE_KEY = process.env.REACT_APP_GOOGLE_KEY;
const LIBRARIES = ["places"];
const mapContainerStyle = { width: "100vw", height: "100vh" };
const mapStyles = [
  { featureType: "road", elementType: "geometry.fill", stylers: [{ color: "#f6c6dc" }] },
  { featureType: "water", elementType: "geometry.fill", stylers: [{ color: "#613659" }] },
  { featureType: "landscape", elementType: "geometry.fill", stylers: [{ color: "#eae6e7" }] },
];

const NavigationPage = () => {
  const [currentLocation, setCurrentLocation] = useState(null);
  const [destination, setDestination] = useState("");
  const [directions, setDirections] = useState(null);
  const [stopMarker, setStopMarker] = useState(null);
  const [destMarker, setDestMarker] = useState(null);

  const autocompleteRef = useRef(null);
  const socketRef = useRef(null);
  const navsocketRef = useRef(null);
  const recognitionRef = useRef(null);
  const voiceRef = useRef(null);

  // Voice setup
  useEffect(() => {
    const pick = () => {
      const v = window.speechSynthesis.getVoices();
      if (!v.length) return;
      voiceRef.current =
        v.find(x => x.name === "Google Australian English") ||
        v.find(x => x.lang === "en-AU") ||
        v.find(x => /female|zira|samantha|susan|karen/i.test(x.name)) ||
        v[0];
    };
    pick();
    window.speechSynthesis.onvoiceschanged = pick;
  }, []);

  const speak = (text, onDone) => {
    if (!text) { onDone?.(); return; }
    window.speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    if (voiceRef.current) utt.voice = voiceRef.current;
    utt.lang = "en-AU";
    utt.onend = () => onDone?.();
    utt.onerror = () => onDone?.();
    window.speechSynthesis.speak(utt);
  };

  // Get current location
  useEffect(() => {
    navigator.geolocation.getCurrentPosition(
      (pos) => setCurrentLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => alert("Could not get location.")
    );
  }, []);

  // Nav websocket + GPS polling
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/navigation");
    navsocketRef.current = ws;
    ws.onopen = () => console.log("NavSocket open");
    ws.onmessage = (event) => speak(event.data, null);

    const interval = setInterval(() => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          if (ws.readyState === WebSocket.OPEN)
            ws.send(JSON.stringify({ lat: pos.coords.latitude, lng: pos.coords.longitude }));
        },
        (err) => console.error("Geo error:", err),
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    }, 1000);

    return () => { clearInterval(interval); ws.close(); };
  }, []);

  const setupAudioCapture = () => {
    const ws = new WebSocket("ws://localhost:8000/ws");
    socketRef.current = ws;
    let waiting = false;

    ws.onopen = () => console.log("WS open");
    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        if (parsed.new_dest) setDestMarker(parsed.new_dest);
        if (parsed.stop) setStopMarker(parsed.stop);
        if (parsed.route?.length && window.google) {
          const origin = parsed.route[parsed.route.length - 1];
          const dest = parsed.route[0];
          new window.google.maps.DirectionsService().route(
            { origin, destination: dest, travelMode: window.google.maps.TravelMode.DRIVING },
            (result, status) => { if (status === "OK") setDirections(result); }
          );
        }
        if (parsed.text) {
          waiting = false;
          speak(parsed.text, () => ws.readyState === WebSocket.OPEN && ws.send("done"));
          return;
        }
      } catch (_) {}
      waiting = false;
      speak(event.data, () => ws.readyState === WebSocket.OPEN && ws.send("done"));
    };
    ws.onerror = (e) => console.error("WS error:", e);

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { console.warn("Speech recognition not supported"); return; }
    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.onresult = (e) => {
      if (waiting) return;
      const t = e.results[e.results.length - 1][0].transcript.trim();
      if (t && ws.readyState === WebSocket.OPEN) { waiting = true; ws.send(t); }
    };
    recognition.onerror = (e) => { if (e.error !== "aborted") console.error("Speech:", e.error); };
    recognition.onend = () => { if (recognitionRef.current) recognition.start(); };
    recognitionRef.current = recognition;
    recognition.start();
  };

  const startNavigation = async () => {
    if (!currentLocation || !window.google) return;
    let dest = destination;
    if (autocompleteRef.current?.getPlace()?.formatted_address) {
      dest = autocompleteRef.current.getPlace().formatted_address;
      setDestination(dest);
    }
    if (!dest) return;

    setupAudioCapture();

    new window.google.maps.DirectionsService().route(
      { origin: currentLocation, destination: dest, travelMode: window.google.maps.TravelMode.DRIVING },
      async (result, status) => {
        if (status !== "OK") { console.error("Directions:", status); return; }
        setDirections(result);
        const leg = result.routes[0].legs[0];
        try {
          await fetch("http://localhost:8000/destination", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              start: { lat: currentLocation.lat, lng: currentLocation.lng },
              curr:  { lat: currentLocation.lat, lng: currentLocation.lng },
              dest:  { lat: leg.end_location.lat(), lng: leg.end_location.lng(), address: dest, name: dest },
              duration: leg.duration.text,
              distance: leg.distance.text,
            }),
          });
        } catch (e) { console.error("Backend error:", e); }
      }
    );
  };

  return (
    <LoadScript googleMapsApiKey={GOOGLE_KEY} libraries={LIBRARIES}>
      <GoogleMap
        mapContainerStyle={mapContainerStyle}
        zoom={15}
        center={currentLocation || { lat: 20.5937, lng: 78.9629 }}
        options={{ styles: mapStyles, minZoom: 3, maxZoom: 20 }}
      >
        {directions && <DirectionsRenderer directions={directions} />}
        {stopMarker && <Marker position={stopMarker} label="S" />}
        {destMarker && <Marker position={destMarker} label="D" />}
      </GoogleMap>

      <div className="controls">
        <Autocomplete
          onLoad={(a) => (autocompleteRef.current = a)}
          onPlaceChanged={() => {
            const place = autocompleteRef.current?.getPlace();
            if (place?.formatted_address) setDestination(place.formatted_address);
          }}
        >
          <input
            type="text"
            placeholder="Enter destination"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          />
        </Autocomplete>
        <button onClick={startNavigation}>Start Navigation</button>
      </div>
    </LoadScript>
  );
};

export default NavigationPage;
