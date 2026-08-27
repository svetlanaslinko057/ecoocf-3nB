import React, { useMemo } from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { toast } from 'sonner';
import axios from 'axios';
import LeadCard from './LeadCard';
import { LEAD_PIPELINE, STATUS_THEME, statusLabel } from './leadConstants';
import { API_URL } from '../../App';

/**
 * Full Kanban board. Stateless about data — receives `columns` (the
 * /api/leads/kanban payload) and a refresh callback. Drag handling lives
 * here because we want optimistic-UI in the parent's `columns` state.
 */
const LeadKanbanBoard = ({ columns, lang, managers, canReassign, onCardOpen, onReassign, onRefresh, role, currentUserId }) => {
  // Pre-compute drop permissions per column. Managers can only drop INTO
  // their own leads' columns, but the constraint is per-card (managerId === uid).
  const canMoveAny = ['admin','master_admin','owner','team_lead'].includes((role||'').toLowerCase());

  const handleDragEnd = async (result) => {
    const { destination, source, draggableId } = result;
    if (!destination) return;
    if (destination.droppableId === source.droppableId && destination.index === source.index) return;

    const fromStatus = source.droppableId;
    const toStatus   = destination.droppableId;
    if (fromStatus === toStatus) return;

    // Find the lead card
    const lead = (columns.find(c => c.status === fromStatus)?.items || [])
      .find(l => l.id === draggableId);
    if (!lead) return;

    // Manager guard
    if (!canMoveAny) {
      if (lead.managerId && currentUserId && lead.managerId !== currentUserId) {
        toast.error('You can only move your own leads');
        return;
      }
    }

    try {
      await axios.patch(`${API_URL}/api/leads/${draggableId}/status`, {
        status: toStatus,
        reason: 'kanban_drag',
      });
      toast.success(`→ ${statusLabel(lang, toStatus)}`, { duration: 1800 });
      onRefresh && onRefresh();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Move failed';
      toast.error(msg);
      onRefresh && onRefresh(); // ensure UI returns to truth
    }
  };

  return (
    <div data-testid="leads-kanban-board" className="w-full">
      <DragDropContext onDragEnd={handleDragEnd}>
        <div className="flex gap-3 overflow-x-auto pb-4 -mx-2 px-2">
          {columns.map((col) => {
            const theme = STATUS_THEME[col.status] || STATUS_THEME.new;
            return (
              <div
                key={col.status}
                className="shrink-0 w-[300px] rounded-2xl bg-[#FAFAFA] border border-[#E4E4E7] flex flex-col"
                data-testid={`leads-kanban-col-${col.status}`}
                style={{ maxHeight: 'calc(100vh - 280px)' }}
              >
                {/* Column header */}
                <div
                  className="px-3 py-2.5 rounded-t-2xl flex items-center justify-between gap-2"
                  style={{ backgroundColor: theme.soft, borderTop: `3px solid ${theme.hex}` }}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: theme.dot }} />
                    <span className="text-[13px] font-semibold truncate" style={{ color: theme.text }}>
                      {col.label || statusLabel(lang, col.status)}
                    </span>
                  </div>
                  <span className="text-[11px] font-bold tabular-nums px-2 py-0.5 rounded-full bg-white shadow-sm"
                        style={{ color: theme.text }}>
                    {col.count}
                  </span>
                </div>

                {/* Drop area */}
                <Droppable droppableId={col.status}>
                  {(provided, snapshot) => (
                    <div
                      ref={provided.innerRef}
                      {...provided.droppableProps}
                      className={`flex-1 overflow-y-auto p-2 space-y-2 transition-colors ${snapshot.isDraggingOver ? 'bg-[#EEF2FF]' : ''}`}
                      data-testid={`leads-kanban-drop-${col.status}`}
                    >
                      {(col.items || []).map((lead, idx) => (
                        <Draggable key={lead.id} draggableId={lead.id} index={idx}>
                          {(p, s) => (
                            <div
                              ref={p.innerRef}
                              {...p.draggableProps}
                              {...p.dragHandleProps}
                              style={p.draggableProps.style}
                            >
                              <LeadCard
                                lead={lead}
                                lang={lang}
                                managers={managers}
                                canReassign={canReassign}
                                isDragging={s.isDragging}
                                onOpen={() => onCardOpen && onCardOpen(lead)}
                                onReassign={onReassign}
                              />
                            </div>
                          )}
                        </Draggable>
                      ))}
                      {provided.placeholder}
                      {(col.items || []).length === 0 && !snapshot.isDraggingOver ? (
                        <div className="text-center text-[11px] text-[#A1A1AA] italic py-6">empty</div>
                      ) : null}
                      {col.hasMore ? (
                        <div className="text-center text-[10px] text-[#71717A] py-1.5">
                          + more (use filters)
                        </div>
                      ) : null}
                    </div>
                  )}
                </Droppable>
              </div>
            );
          })}
        </div>
      </DragDropContext>
    </div>
  );
};

export default LeadKanbanBoard;
