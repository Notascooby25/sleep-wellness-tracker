const fs = require('fs');
let content = fs.readFileSync('backend/app/database.py', 'utf8');
content = content.replace(
  '        # Step 2: Set the flag to true for the specific activities',
  \`        # Step 1.5: Add ignore_in_reports column
        conn.execute(text("ALTER TABLE activities ADD COLUMN IF NOT EXISTS ignore_in_reports BOOLEAN DEFAULT FALSE NOT NULL"))
        
        # Step 2: Set the flag to true for the specific activities\`
);
fs.writeFileSync('backend/app/database.py', content);
