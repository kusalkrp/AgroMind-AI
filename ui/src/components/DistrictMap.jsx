import React from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";

// Fix Leaflet's default icon path issue with bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// 10 key Sri Lankan district lat/lng pairs
const DISTRICTS = [
  { name: "Colombo",      lat: 6.9271,  lng: 79.8612 },
  { name: "Kandy",        lat: 7.2906,  lng: 80.6337 },
  { name: "Galle",        lat: 6.0535,  lng: 80.2210 },
  { name: "Jaffna",       lat: 9.6615,  lng: 80.0255 },
  { name: "Anuradhapura", lat: 8.3114,  lng: 80.4037 },
  { name: "Polonnaruwa",  lat: 7.9403,  lng: 81.0188 },
  { name: "Kurunegala",   lat: 7.4863,  lng: 80.3647 },
  { name: "Ratnapura",    lat: 6.6828,  lng: 80.3992 },
  { name: "Matara",       lat: 5.9485,  lng: 80.5353 },
  { name: "Badulla",      lat: 6.9934,  lng: 81.0550 },
];

/**
 * DistrictMap — react-leaflet map centred on Sri Lanka.
 * Shows 10 district pins; highlights the currently selected district.
 */
export default function DistrictMap({ selectedDistrict = null, onDistrictClick }) {
  return (
    <MapContainer
      center={[7.8731, 80.7718]}
      zoom={7}
      style={{ height: "100%", width: "100%", borderRadius: "0.5rem" }}
      scrollWheelZoom={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {DISTRICTS.map((d) => {
        const isSelected =
          selectedDistrict &&
          d.name.toLowerCase() === selectedDistrict.toLowerCase();

        const icon = isSelected
          ? L.divIcon({
              className: "",
              html: `<div style="
                background:#16a34a;color:white;border-radius:50%;
                width:28px;height:28px;display:flex;align-items:center;
                justify-content:center;font-size:11px;font-weight:bold;
                border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,.4)">
                ${d.name[0]}
              </div>`,
              iconSize: [28, 28],
              iconAnchor: [14, 14],
            })
          : new L.Icon.Default();

        return (
          <Marker
            key={d.name}
            position={[d.lat, d.lng]}
            icon={icon}
            eventHandlers={{
              click: () => onDistrictClick && onDistrictClick(d.name),
            }}
          >
            <Popup>
              <strong>{d.name}</strong>
              {isSelected && <span className="ml-1 text-green-600"> ✓ selected</span>}
            </Popup>
          </Marker>
        );
      })}
    </MapContainer>
  );
}
