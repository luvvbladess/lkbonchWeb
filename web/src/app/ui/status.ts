import { Component, input } from '@angular/core';
import { MatIcon } from '@angular/material/icon';

@Component({
  selector: 'app-status',
  imports: [MatIcon],
  template: `
    <span class="status" [attr.data-tone]="tone()">
      <mat-icon aria-hidden="true">{{ icon() }}</mat-icon>
      {{ label() }}
    </span>
  `,
})
export class StatusChip {
  readonly tone = input('neutral');
  readonly icon = input.required<string>();
  readonly label = input.required<string>();
}
