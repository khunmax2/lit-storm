"""Postgres tells listeners when the queue or a Run changes

Revision ID: 0012
Revises: 0011

Two channels, both sent on commit and only then (litstorm.notify):

- `litstorm_queue`: a Run became queued, or left a slot. The Worker wakes
  to claim instead of waiting out its poll.
- `litstorm_run`, payload the Run's id: the Run's status, stage or notes
  changed, or it has a new event. The API's live streams wake to send it.
  A lease renewal alone sends nothing.
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        create function litstorm_notify_run() returns trigger language plpgsql as $$
        begin
          if tg_table_name = 'run_events' then
            perform pg_notify('litstorm_run', new.run_id::text);
            return null;
          end if;
          if tg_op = 'INSERT' then
            if new.status = 'queued' then
              perform pg_notify('litstorm_queue', '');
            end if;
            return null;
          end if;
          if new.status is distinct from old.status
             and (new.status = 'queued' or old.status in ('running', 'cancelling')) then
            perform pg_notify('litstorm_queue', '');
          end if;
          if (new.status, new.stage, new.notes, new.reason, new.report_title)
             is distinct from (old.status, old.stage, old.notes, old.reason, old.report_title) then
            perform pg_notify('litstorm_run', new.id::text);
          end if;
          return null;
        end $$;
        """
    )
    op.execute(
        "create trigger runs_notify after insert or update on runs "
        "for each row execute function litstorm_notify_run()"
    )
    op.execute(
        "create trigger run_events_notify after insert on run_events "
        "for each row execute function litstorm_notify_run()"
    )


def downgrade():
    op.execute("drop trigger run_events_notify on run_events")
    op.execute("drop trigger runs_notify on runs")
    op.execute("drop function litstorm_notify_run()")
