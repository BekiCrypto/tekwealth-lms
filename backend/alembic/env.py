import os
import sys
from logging.config import fileConfig

# Adjust sys.path to include the project root (parent of 'backend' directory)
# This allows Alembic to find the 'backend' package and its modules.
# Assuming this env.py is in backend/alembic/env.py, project_root is two levels up.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# Import Base from your database configuration and all your models
from backend.core.database import Base  # Your SQLAlchemy Base
from backend.models import ( # Import all model modules to register them with Base.metadata
    user_model,
    course_model,
    user_progress_model,
    certificate_model,
    subscription_model,
    payment_model,
    referral_model
)
# Set target_metadata to your Base's metadata
target_metadata = Base.metadata

# Import settings to get DATABASE_URL
from backend.core.config import settings


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # Use DATABASE_URL from settings
    url = settings.DATABASE_URL
    if not url:
        raise ValueError("DATABASE_URL is not set in the environment or config.")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Use DATABASE_URL from settings for online mode
    db_url = settings.DATABASE_URL
    if not db_url:
        raise ValueError("DATABASE_URL is not set in the environment or config for online migrations.")

    # Create a new section in the config object for Alembic, based on our settings
    # This avoids needing engine_from_config which reads directly from alembic.ini's [alembic] section
    # We directly provide the URL.

    # Minimal config for connectable, using the URL from settings
    configuration = config.get_section(config.config_ini_section, {})
    configuration['sqlalchemy.url'] = db_url # Override with our settings' URL

    connectable = engine_from_config(
        configuration, # Use the modified configuration
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
