export interface ViolationEvent {
  id: string;
  timestamp: string;
  zone: string;
  maps_url: string;
  address: string;
  image_url: string;
  status: string;
  notes: string;
  lat?: number;
  lng?: number;
}
