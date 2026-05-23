const { Client } = require('pg');

async function test() {
  const connectionString = process.env.SUPABASE_DB_URL || process.env.DATABASE_URL;
  if (!connectionString) {
    console.error('SUPABASE_DB_URL ou DATABASE_URL nao configurada.');
    process.exitCode = 1;
    return;
  }

  const client = new Client({ connectionString, connectionTimeoutMillis: 5000 });
  try {
    await client.connect();
    console.log('Conexao PostgreSQL OK.');
  } catch (error) {
    console.error('Falha ao conectar:', error.message);
    process.exitCode = 1;
  } finally {
    await client.end().catch(() => {});
  }
}

test();
