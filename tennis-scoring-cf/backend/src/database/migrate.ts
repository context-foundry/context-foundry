import fs from 'fs';
import path from 'path';
import pool from './pool';

const migrationsDir = path.join(__dirname, 'migrations');

async function runMigrations(direction: 'up' | 'down' = 'up') {
  try {
    console.log(`Running migrations ${direction}...`);

    const files = fs
      .readdirSync(migrationsDir)
      .filter((f) => f.endsWith('.sql'))
      .sort();

    if (direction === 'down') {
      files.reverse();
    }

    for (const file of files) {
      const filePath = path.join(migrationsDir, file);
      const sql = fs.readFileSync(filePath, 'utf-8');

      console.log(`Executing ${file}...`);

      if (direction === 'down') {
        // For down migrations, we'd need separate down SQL files
        // For now, we'll just skip or implement table drops
        console.log(`Down migrations not implemented for ${file}`);
        continue;
      }

      await pool.query(sql);
      console.log(`✓ ${file} completed`);
    }

    console.log('All migrations completed successfully!');
    process.exit(0);
  } catch (error) {
    console.error('Migration error:', error);
    process.exit(1);
  }
}

const direction = process.argv[2] as 'up' | 'down';
runMigrations(direction || 'up');
