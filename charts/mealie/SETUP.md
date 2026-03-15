# Postgres or SQLite

Mealie uses SQLite by default. It simplifies backups and does not require a separate service. However, you won't be able to use fuzzy search and miss out on some performance improvements. If you aren't serving multiple users, and don't mind losing access to some features, stick with SQLite. If you choose to use Postgres, you can use the included Postgres service, or use an already existing Postgres database.

## How to enable the built in Postgres service

In the values file, set DB_ENGINE in env under mealie from sqlite to Postgres. Under the Postgres section, set enable from false to true. If you want to change any of the other Postgres environment variables, make sure to also change them as well in the env section under mealie. Leave PGDATA alone, as it specifies the location where Postgres stores its data files, and the database will wipe itself every time Postgres is restarted.

## OpenAI

In the values file, you can add your OpenAI API key to the OPENAI_API_KEY field to enable AI features. You must have a valid OpenAI API key for these features to work. Make sure to also set the OPENAI_MODEL field to the desired model (e.g., gpt-4.1), and configure OPENAI_BASE_URL if you are using a custom endpoint.