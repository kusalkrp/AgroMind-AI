import React from "react";
import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import "./DistrictMap.css";

// Fix Leaflet's default icon path issue with bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

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

export default function DistrictMap({ selectedDistrict = null, onDistrictClick }) {
  return (
    <div className="map-wrapper glass-panel">
      <MapContainer
        center={[7.8731, 80.7718]}
        zoom={7}
        className="premium-map"
        scrollWheelZoom={false}
      >
        {/* Dark Mode Tiles for Modern Aesthetic */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        {DISTRICTS.map((d) => {
          const isSelected =
            selectedDistrict &&
            d.name.toLowerCase() === selectedDistrict.toLowerCase();

          const icon = L.divIcon({
            className: "custom-leaflet-icon",
            html: `<div class="marker-pin ${isSelected ? 'selected' : ''}">
              ${d.name[0]}
              ${isSelected ? '<div class="pulse-ring"></div>' : ''}
            </div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16],
          });

          return (
            <Marker
              key={d.name}
              position={[d.lat, d.lng]}
              icon={icon}
              eventHandlers={{
                click: () => onDistrictClick && onDistrictClick(d.name),
              }}
            >
              <Popup className="premium-popup">
                <div className="popup-content">
                  <span className="popup-title">{d.name}</span>
                  {isSelected && <span className="popup-status text-gradient">Active</span>}
                </div>
              </Popup>
            </Marker>
          );
        })}
      </MapContainer>
    </div>
  );
}
