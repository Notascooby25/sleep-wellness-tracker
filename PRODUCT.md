# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Personal use (self-hosted). The primary user is the developer, tracking their own daily wellness and sleep data.

## Product Purpose
To track daily sleep, mood, activities, and biometrics in a unified dashboard.

## Positioning
Correlates objective Garmin hardware metrics (HRV, Sleep, Body Battery) with subjective, user-entered data (mood, activities) to provide holistic personal insights that the native Garmin Connect app does not offer.

## Operating Context
Self-hosted on an Intel NUC via Docker Compose. Objective data is fetched automatically from Garmin Connect via background syncs, while subjective mood and activity data is entered manually by the user.

## Capabilities and Constraints
- **Stack**: SvelteKit frontend, FastAPI backend, PostgreSQL database.
- **Constraints**: Must preserve existing data ingestion pipelines (Garmin autosync), database schema, and cron backups. Future design work must not break existing functionality.
- **Visuals**: Open to design iterations and suggestions, provided core features remain stable.

## Evidence on Hand
- Working data ingestion from Garmin Connect API.
- Working image upload system for mood attachments.
- Existing database schema with historical biometric and subjective data.
