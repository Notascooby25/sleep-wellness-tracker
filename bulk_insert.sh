#!/usr/bin/env bash

set -u

API_BASE="${API_BASE:-http://localhost:8000}"

if ! command -v jq >/dev/null 2>&1; then
	echo "Error: jq is required for this script. Install jq and run again."
	exit 1
fi

declare -A CAT_ID

resolve_category_id() {
	local category_name="$1"
	local category_id
	category_id="$(curl -sS "${API_BASE}/categories/" | jq -r --arg n "$category_name" '.[] | select(.name == $n) | .id' | head -n 1)"

	if [[ -z "$category_id" || "$category_id" == "null" ]]; then
		echo "Error: category not found: $category_name"
		return 1
	fi

	CAT_ID["$category_name"]="$category_id"
	return 0
}

resolve_with_fallback() {
	local primary_name="$1"
	local fallback_name="$2"
	if resolve_category_id "$primary_name"; then
		return 0
	fi
	if [[ -n "$fallback_name" ]]; then
		resolve_category_id "$fallback_name" || true
		if [[ -n "${CAT_ID[$fallback_name]:-}" ]]; then
			CAT_ID["$primary_name"]="${CAT_ID[$fallback_name]}"
			echo "Using fallback category '$fallback_name' for '$primary_name'"
		fi
	fi
}

create_activity() {
	local category_name="$1"
	local activity_name="$2"
	local category_id="${CAT_ID[$category_name]:-}"

	if [[ -z "$category_id" ]]; then
		echo "Skip: unresolved category for activity '$activity_name'"
		return 1
	fi

	local http_code
	http_code="$(curl -sS -o /dev/null -w "%{http_code}" -X POST "${API_BASE}/activities/" -H "Content-Type: application/json" -d "{\"name\":\"${activity_name}\",\"category_id\":${category_id}}")"

	if [[ "$http_code" =~ ^2 ]]; then
		echo "OK   [$category_name] $activity_name"
	else
		echo "FAIL [$category_name] $activity_name (HTTP $http_code)"
	fi
}

resolve_with_fallback "Lifestyle" ""
resolve_with_fallback "Headache Issues" "Headaches"
resolve_with_fallback "Health" ""
resolve_with_fallback "Before Sleep" ""
resolve_with_fallback "During Sleep" "Morning Check In"

# LIFESTYLE
create_activity "Lifestyle" "Reading"
create_activity "Lifestyle" "Relax"
create_activity "Lifestyle" "DIY Gardening"
create_activity "Lifestyle" "Workout"
create_activity "Lifestyle" "Cycling"
create_activity "Lifestyle" "Walk"
create_activity "Lifestyle" "Exercise"
create_activity "Lifestyle" "Run"
create_activity "Lifestyle" "Gardening"
create_activity "Lifestyle" "Acupuncture"
create_activity "Lifestyle" "Physio"

# HEADACHE ISSUES
create_activity "Headache Issues" "Headache"
create_activity "Headache Issues" "Migraine"
create_activity "Headache Issues" "Pain in Left Side of Head"
create_activity "Headache Issues" "Pain Front of Head"
create_activity "Headache Issues" "Pain Right Side of Head"
create_activity "Headache Issues" "Jaw / Teeth Pain Left Side"
create_activity "Headache Issues" "Jaw / Teeth Pain Right Side"
create_activity "Headache Issues" "Pressure in Head"
create_activity "Headache Issues" "Brain Fog"
create_activity "Headache Issues" "Blurred Vision"
create_activity "Headache Issues" "Back Right"
create_activity "Headache Issues" "Pain Back Left of Head"
create_activity "Headache Issues" "Strain Lower Right Throat"
create_activity "Headache Issues" "Strain Lower Left Throat"

# HEALTH
create_activity "Health" "Anxious / Anxiety Shaking"
create_activity "Health" "Legs Hurting / Aching"
create_activity "Health" "Fatigue / Ache"
create_activity "Health" "No Energy"
create_activity "Health" "Ear Humming Left"
create_activity "Health" "Ear Humming Right"
create_activity "Health" "Skin Peeling on Hands"
create_activity "Health" "Left Shoulder / Arm / Neck"
create_activity "Health" "Right Side Shoulder / Neck"
create_activity "Health" "Back Pain - Lower"
create_activity "Health" "Eat Healthy"
create_activity "Health" "Ill / Injured"
create_activity "Health" "Foot - Heel"
create_activity "Health" "PeakFlow Test"
create_activity "Health" "Wheezy / Short of Breath"
create_activity "Health" "Cold"
create_activity "Health" "Right Ear Ache / Pain"
create_activity "Health" "Left Ear Ache"
create_activity "Health" "Acid Reflux"
create_activity "Health" "Bloated"
create_activity "Health" "Allergy / Hayfever"

# BEFORE SLEEP
create_activity "Before Sleep" "Stress"
create_activity "Before Sleep" "Exercise"
create_activity "Before Sleep" "Shower or Bath"
create_activity "Before Sleep" "Self-Care"
create_activity "Before Sleep" "Anxiety"
create_activity "Before Sleep" "Breathing Exercises"
create_activity "Before Sleep" "Meditation"
create_activity "Before Sleep" "Screen Time"
create_activity "Before Sleep" "Alcohol"
create_activity "Before Sleep" "Food"
create_activity "Before Sleep" "Caffeine"
create_activity "Before Sleep" "Work"
create_activity "Before Sleep" "Busy Schedule"
create_activity "Before Sleep" "Relaxation"
create_activity "Before Sleep" "Reading"
create_activity "Before Sleep" "Nap"
create_activity "Before Sleep" "Journaling"
create_activity "Before Sleep" "Travel"
create_activity "Before Sleep" "Supplement"
create_activity "Before Sleep" "Pain"
create_activity "Before Sleep" "Medication"
create_activity "Before Sleep" "Illness"

# DURING SLEEP
create_activity "During Sleep" "Bathroom"
create_activity "During Sleep" "Tossing and Turning"
create_activity "During Sleep" "Fell Asleep Quickly"
create_activity "During Sleep" "Interrupted Sleep"
create_activity "During Sleep" "Restless Mind"
create_activity "During Sleep" "Restful Sleep"
create_activity "During Sleep" "Not Tired"
create_activity "During Sleep" "Insomnia"
create_activity "During Sleep" "Sleep Music"
create_activity "During Sleep" "Woke Up Refreshed"
create_activity "During Sleep" "Soundscapes"
create_activity "During Sleep" "Sleep Stories"
create_activity "During Sleep" "Shared Bed"
create_activity "During Sleep" "Nightmare"
create_activity "During Sleep" "Dream"
create_activity "During Sleep" "Light"
create_activity "During Sleep" "Noise"
create_activity "During Sleep" "Warm Room Temperature"
create_activity "During Sleep" "Cool Room Temperature"
create_activity "During Sleep" "Children"
create_activity "During Sleep" "Pain"
create_activity "During Sleep" "Pets"
create_activity "During Sleep" "Health Condition"
