export type Category = {
  id: number;
  name: string;
  require_rating?: number;
  rating_label?: string | null;
};

export type Activity = {
  id: number;
  name: string;
  category_id?: number | null;
  is_archived?: boolean; // Indicates if the activity is archived
  deprecated_at?: string | null;
  supports_position?: boolean;
};

export type ActivityDetailInput = {
  activity_id: number;
  position?: string | null;
  severity?: number | null;
  quantity_numeric?: number | null;
  quantity_unit?: string | null;
};

export type MoodEntry = {
  id?: number;
  mood_score: number | null;
  notes?: string | null;
  image_url?: string | null;
  image_urls?: string[] | null;
  timestamp: string;
  activity_ids: number[];
  activity_details?: ActivityDetailInput[];
  subjective_sleep_rating?: number | null;
  created_at?: string;
};

export type GarminLatestWrap<T> = {
  data: T | null;
};
