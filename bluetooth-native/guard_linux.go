package main

import (
	"context"
	"fmt"
	"os"
	"strings"
	"time"
)

// The guard is a separate process, deliberately independent of BlueZ, D-Bus,
// SDL and the backend event queue. EVIOCGKEY does not consume input events.
type guardGesture struct {
	armed       bool
	combo, menu time.Time
}

func (g *guardGesture) update(keys [768]bool, now time.Time) string {
	if !g.armed {
		if !keys[314] && !keys[315] && !keys[316] {
			g.armed = true
		}
		return ""
	}
	if keys[314] && keys[315] {
		if g.combo.IsZero() {
			g.combo = now
		}
		if now.Sub(g.combo) >= 2*time.Second {
			return "START_SELECT"
		}
	} else {
		g.combo = time.Time{}
	}
	if keys[316] {
		if g.menu.IsZero() {
			g.menu = now
		}
		// MENU la nut dung phien Bluetooth (thay cho B, vi B la nut test).
		// Giu 2 giay, bang START+SELECT, de nguoi dung khong phai nho hai
		// moc thoi gian khac nhau.
		if now.Sub(g.menu) >= 2*time.Second {
			return "MENU_HOLD"
		}
	} else {
		g.menu = time.Time{}
	}
	return ""
}

func runGuard(ctx context.Context, stateFile, cancelFile string, parent int, logKeys bool) error {
	d, e := chooseInput()
	if e != nil {
		return e
	}
	defer d.close()
	fmt.Printf("Exit guard input: %s %q; no exclusive grab\n", d.path, d.name)
	gesture := guardGesture{}
	lastKeys := [768]bool{}
	start := time.Now()
	lastBeat := time.Time{}
	sequence := 0
	ticker := time.NewTicker(40 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return nil
		case now := <-ticker.C:
			if parent > 0 && os.Getppid() != parent {
				return nil
			}
			keys, err := d.keySnapshot()
			if err != nil {
				return fmt.Errorf("exit guard key query: %w", err)
			}
			if logKeys && keys != lastKeys {
				var held []string
				for code, down := range keys {
					if down {
						held = append(held, fmt.Sprint(code))
					}
				}
				fmt.Printf("Exit test +%s pressed Linux keys: [%s]\n", now.Sub(start).Round(time.Millisecond), strings.Join(held, ","))
				lastKeys = keys
			}
			if reason := gesture.update(keys, now); reason != "" {
				fmt.Println("Independent exit guard:", reason)
				if e := writeFileAtomic(cancelFile, reason); e != nil {
					return e
				}
				return nil
			}
			if now.Sub(lastBeat) >= 250*time.Millisecond {
				sequence++
				if e := writeFileAtomic(stateFile, fmt.Sprintf("ready %d", sequence)); e != nil {
					return e
				}
				lastBeat = now
			}
		}
	}
}
