"""initial tables

Revision ID: 001
Revises: 
Create Date: 2026-10-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    user_role_enum = postgresql.ENUM('student', 'teacher', 'admin', name='userrole', create_type=False)
    user_level_enum = postgresql.ENUM('basic', 'intermediate', 'advanced', name='userlevel', create_type=False)
    message_role_enum = postgresql.ENUM('user', 'assistant', 'system', name='messagerole', create_type=False)
    
    # Create enums
    op.execute("CREATE TYPE userrole AS ENUM ('student', 'teacher', 'admin')")
    op.execute("CREATE TYPE userlevel AS ENUM ('basic', 'intermediate', 'advanced')")
    op.execute("CREATE TYPE messagerole AS ENUM ('user', 'assistant', 'system')")
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('role', user_role_enum, nullable=False, server_default='student'),
        sa.Column('level', user_level_enum, nullable=False, server_default='basic'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_active', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('settings', postgresql.JSONB, nullable=False, server_default=sa.text('{}')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    
    # Create indexes for users
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_username', 'users', ['username'])
    
    # Create chat_sessions table
    op.create_table(
        'chat_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('level', sa.String(20), nullable=False, server_default='basic'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('metadata', postgresql.JSONB, nullable=False, server_default=sa.text('{}')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for chat_sessions
    op.create_index('idx_chat_sessions_user', 'chat_sessions', ['user_id'])
    
    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', message_role_enum, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('code_blocks', postgresql.JSONB, nullable=False, server_default=sa.text('[]')),
        sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for chat_messages
    op.create_index('idx_chat_messages_session', 'chat_messages', ['session_id'])


def downgrade() -> None:
    # Drop tables
    op.drop_index('idx_chat_messages_session', table_name='chat_messages')
    op.drop_table('chat_messages')
    
    op.drop_index('idx_chat_sessions_user', table_name='chat_sessions')
    op.drop_table('chat_sessions')
    
    op.drop_index('idx_users_username', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_table('users')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS messagerole")
    op.execute("DROP TYPE IF EXISTS userlevel")
    op.execute("DROP TYPE IF EXISTS userrole")
