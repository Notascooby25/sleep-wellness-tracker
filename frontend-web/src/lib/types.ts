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
};

export type MoodEntry = {
  id?: number;
  mood_score: number | null;
  notes?: string | null;
  image_url?: string | null;
  timestamp: string;
  activity_ids: number[];
  created_at?: string;
};

export type GarminLatestWrap<T> = {
  data: T | null;
};
