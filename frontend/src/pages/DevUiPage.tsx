import { useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Modal } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { TabPanel, Tabs } from '@/components/ui/Tabs';
import { Table, Td, Th, Tr } from '@/components/ui/Table';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { ToastStack } from '@/components/ui/Toast';

/**
 * Storybook-lite (S18-001): только в dev, в прод-бандл не попадает.
 */
export function DevUiPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [tab, setTab] = useState('components');
  const [toasts, setToasts] = useState<{ id: string; message: string }[]>([]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">UI kit</h1>
        <ThemeToggle />
      </div>

      <Tabs
        label="UI sections"
        value={tab}
        onChange={setTab}
        items={[
          { id: 'components', label: 'Components' },
          { id: 'tokens', label: 'Tokens' },
        ]}
      />
      <TabPanel id="components" active={tab === 'components'}>
        <div className="flex flex-col gap-4">
          <Card title="Badges">
            <div className="flex flex-wrap gap-2">
              <Badge>neutral</Badge>
              <Badge tone="success">success</Badge>
              <Badge tone="warning">warning</Badge>
              <Badge tone="danger">danger</Badge>
              <Badge tone="info">info</Badge>
            </div>
          </Card>

          <Card title="Skeleton">
            <Skeleton lines={3} />
          </Card>

          <Card title="Table">
            <Table caption="Demo table">
              <thead>
                <Tr>
                  <Th>Task</Th>
                  <Th>Status</Th>
                </Tr>
              </thead>
              <tbody>
                <Tr>
                  <Td>Loops</Td>
                  <Td>
                    <Badge tone="success">done</Badge>
                  </Td>
                </Tr>
              </tbody>
            </Table>
          </Card>

          <Card title="Modal and toast">
            <div className="flex gap-2">
              <Button onClick={() => setModalOpen(true)}>Open modal</Button>
              <Button
                variant="secondary"
                onClick={() =>
                  setToasts((items) => [
                    ...items,
                    { id: String(Date.now()), message: 'Saved' },
                  ])
                }
              >
                Show toast
              </Button>
            </div>
          </Card>
        </div>
      </TabPanel>
      <TabPanel id="tokens" active={tab === 'tokens'}>
        <Card title="Tokens">
          <div className="grid gap-2 text-sm text-slate-700">
            <p>--radius-card: 0.75rem</p>
            <p>--surface / --surface-muted / --border / --app-fg</p>
            <p>brand: #eef2ff, #6366f1, #4338ca</p>
          </div>
        </Card>
      </TabPanel>

      <Modal
        open={modalOpen}
        title="Modal title"
        onClose={() => setModalOpen(false)}
        footer={
          <Button onClick={() => setModalOpen(false)}>Close</Button>
        }
      >
        Modal body with focus management and Escape handling.
      </Modal>

      <ToastStack
        items={toasts}
        onClose={(id) =>
          setToasts((items) => items.filter((item) => item.id !== id))
        }
      />
    </div>
  );
}
