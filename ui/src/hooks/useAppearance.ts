import { useSyncExternalStore } from "react";

export type FontSize = "small" | "default" | "large" | "x-large";
export type ContentDensity = "compact" | "comfortable";

const FONT_SIZE_KEY = "meetingmind-font-size";
const DENSITY_KEY = "meetingmind-density";

function getStoredFontSize(): FontSize {
  return (localStorage.getItem(FONT_SIZE_KEY) as FontSize) || "default";
}

function getStoredDensity(): ContentDensity {
  return (localStorage.getItem(DENSITY_KEY) as ContentDensity) || "comfortable";
}

function applyFontSize(size: FontSize) {
  if (size === "default") {
    document.documentElement.removeAttribute("data-font-size");
  } else {
    document.documentElement.setAttribute("data-font-size", size);
  }
}

function applyDensity(density: ContentDensity) {
  document.documentElement.setAttribute("data-density", density);
}

// External store for font size.
let currentFontSize: FontSize = getStoredFontSize();
const fontSizeListeners = new Set<() => void>();

function subscribeFontSize(cb: () => void) {
  fontSizeListeners.add(cb);
  return () => fontSizeListeners.delete(cb);
}

function getFontSizeSnapshot() {
  return currentFontSize;
}

export function setFontSize(size: FontSize) {
  currentFontSize = size;
  localStorage.setItem(FONT_SIZE_KEY, size);
  applyFontSize(size);
  fontSizeListeners.forEach((cb) => cb());
}

// External store for content density.
let currentDensity: ContentDensity = getStoredDensity();
const densityListeners = new Set<() => void>();

function subscribeDensity(cb: () => void) {
  densityListeners.add(cb);
  return () => densityListeners.delete(cb);
}

function getDensitySnapshot() {
  return currentDensity;
}

export function setDensity(density: ContentDensity) {
  currentDensity = density;
  localStorage.setItem(DENSITY_KEY, density);
  applyDensity(density);
  densityListeners.forEach((cb) => cb());
}

export function useAppearance() {
  const fontSize = useSyncExternalStore(subscribeFontSize, getFontSizeSnapshot);
  const density = useSyncExternalStore(subscribeDensity, getDensitySnapshot);

  return { fontSize, setFontSize, density, setDensity } as const;
}

// Apply immediately so there's no flash of wrong values.
applyFontSize(currentFontSize);
applyDensity(currentDensity);
