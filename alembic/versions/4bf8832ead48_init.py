"""init

Revision ID: 4bf8832ead48
Revises: 
Create Date: 2023-11-04 20:33:02.298113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4bf8832ead48'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('shop',
    sa.Column('id', sa.Integer(), nullable=False, comment='Unique ID'),
    sa.Column('name', sa.String(), nullable=True, comment='Name'),
    sa.Column('address', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='test_name',
    comment='Shop info'
    )
    op.create_table('visitor',
    sa.Column('id', sa.Integer(), nullable=False, comment='Unique ID'),
    sa.Column('name', sa.String(), nullable=True, comment='Name'),
    sa.Column('lastname', sa.String(), nullable=True, comment='Lastname'),
    sa.Column('role', sa.Boolean(), nullable=True, comment='Visitors role'),
    sa.Column('age', sa.Integer(), nullable=True, comment='Visitors age'),
    sa.Column('sex', sa.Integer(), nullable=True, comment='Visitors sex'),
    sa.PrimaryKeyConstraint('id'),
    schema='test_name',
    comment='User of system'
    )
    op.create_table('emotion',
    sa.Column('id', sa.Integer(), nullable=False, comment='Unique ID'),
    sa.Column('visitor_id', sa.Integer(), nullable=False, comment='Сборщик эмоций'),
    sa.Column('placement_point', sa.Integer(), nullable=False, comment='Место сбора данных'),
    sa.Column('anger', sa.Integer(), nullable=True),
    sa.Column('fear', sa.Integer(), nullable=True),
    sa.Column('happy', sa.Integer(), nullable=True),
    sa.Column('neutral', sa.Integer(), nullable=True),
    sa.Column('sadness', sa.Integer(), nullable=True),
    sa.Column('surprized', sa.Integer(), nullable=True),
    sa.Column('datetime', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['placement_point'], ['test_name.shop.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['visitor_id'], ['test_name.visitor.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    schema='test_name',
    comment='Emotions metrics'
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('emotion', schema='test_name')
    op.drop_table('visitor', schema='test_name')
    op.drop_table('shop', schema='test_name')
    # ### end Alembic commands ###