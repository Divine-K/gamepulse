import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Button } from './Button'
import { TextField } from './Field'
import { Menu } from './Menu'
import { Modal } from './Modal'
import { ToastProvider, useToast } from './Toast'
import { Tooltip } from './Tooltip'

describe('Button', () => {
  it('is disabled and busy while loading', () => {
    render(<Button loading>Save</Button>)
    const button = screen.getByRole('button', { name: /save/i })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
  })

  it('fires onClick', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Go</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(onClick).toHaveBeenCalledOnce()
  })
})

describe('TextField', () => {
  it('links label, error and aria-invalid for screen readers', () => {
    render(<TextField label="Email" error="Enter a valid email" />)
    const input = screen.getByLabelText('Email')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Enter a valid email')
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email')
  })

  it('shows the hint when there is no error', () => {
    render(<TextField label="Password" hint="At least 8 characters." />)
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription('At least 8 characters.')
  })
})

describe('Modal', () => {
  function Harness({ onClose = () => {} }: { onClose?: () => void }) {
    const [open, setOpen] = useState(true)
    return (
      <Modal
        open={open}
        onClose={() => {
          setOpen(false)
          onClose()
        }}
        title="Delete game"
        description="This cannot be undone."
      >
        <p>Body</p>
      </Modal>
    )
  }

  it('is a labelled, described dialog', () => {
    render(<Harness />)
    const dialog = screen.getByRole('dialog', { name: 'Delete game' })
    expect(dialog).toHaveAccessibleDescription('This cannot be undone.')
    expect(dialog).toHaveAttribute('open')
  })

  it('closes with the close button', async () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    await userEvent.click(screen.getByRole('button', { name: 'Close dialog' }))
    expect(onClose).toHaveBeenCalled()
  })

  it('light-dismisses on backdrop click but not on content click', async () => {
    const onClose = vi.fn()
    render(<Harness onClose={onClose} />)
    await userEvent.click(screen.getByText('Body'))
    expect(onClose).not.toHaveBeenCalled()
    await userEvent.click(screen.getByRole('dialog', { name: 'Delete game' }))
    expect(onClose).toHaveBeenCalled()
  })
})

describe('Toast', () => {
  function Trigger() {
    const toast = useToast()
    return <button onClick={() => toast.success('Saved', 'All good')}>show</button>
  }

  it('announces in a live region and can be dismissed', async () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    )
    await userEvent.click(screen.getByText('show'))
    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(document.querySelector('[aria-live="polite"]')).toContainElement(
      screen.getByText('Saved'),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss notification' }))
    await waitFor(() => expect(screen.queryByText('Saved')).not.toBeInTheDocument())
  })
})

describe('Menu', () => {
  it('opens, supports keyboard navigation and Escape, and selects', async () => {
    const onA = vi.fn()
    const onB = vi.fn()
    render(
      <Menu
        label="Games"
        items={[
          { id: 'a', label: 'Alpha', selected: true, onSelect: onA },
          { id: 'b', label: 'Beta', selected: false, onSelect: onB },
        ]}
        trigger={(props) => <button {...props}>Pick</button>}
      />,
    )
    const trigger = screen.getByRole('button', { name: 'Pick' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')

    await userEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const alpha = screen.getByRole('menuitemradio', { name: 'Alpha' })
    expect(alpha).toHaveAttribute('aria-checked', 'true')
    expect(alpha).toHaveFocus() // opens focused on the selected item

    await userEvent.keyboard('{ArrowDown}')
    expect(screen.getByRole('menuitemradio', { name: 'Beta' })).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('menu')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus() // focus returns to the trigger

    await userEvent.click(trigger)
    await userEvent.click(screen.getByRole('menuitemradio', { name: 'Beta' }))
    expect(onB).toHaveBeenCalledOnce()
    expect(onA).not.toHaveBeenCalled()
  })
})

describe('Tooltip', () => {
  it('describes its trigger', () => {
    render(
      <Tooltip label="More info">
        <button>Hover me</button>
      </Tooltip>,
    )
    expect(screen.getByRole('button', { name: 'Hover me' })).toHaveAccessibleDescription(
      'More info',
    )
  })
})
