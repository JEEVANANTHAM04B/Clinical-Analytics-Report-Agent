import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ClinicalApprovalCard from '../components/Clinical/ClinicalApprovalCard';
import { summarizeClinicalPlan } from '../components/Clinical/clinicalPlanSummary';

const adverseEventPlan = `### Clinical Analytics Analysis Plan
#### 1. Relevant Tables and Columns
* adsl: USUBJID, TRT01A
* adae: USUBJID
#### 2. Join Conditions
* Join adsl and adae on USUBJID.
#### 3. Derived Calculations
* **Adverse Event Rate By Treatment**:
  Calculate using:
  \`COUNT(DISTINCT adae.USUBJID) / COUNT(DISTINCT adsl.USUBJID) * 100\`
#### 4. Aggregations & Grouping
* Grouping: Group results by \`TRT01A\`.
#### 5. Filtering
* None.`;

const laboratoryPlan = `### Clinical Analytics Analysis Plan
#### 3. Derived Calculations
* **Lab Change From Baseline**:
  Calculate using:
  \`AVG(adlb.CHG), AVG(adlb.PCHG)\`
#### 4. Aggregations & Grouping
* Grouping: Group results by \`TRT01A\`, \`AVISIT\`.
#### 5. Filtering
* Apply filter: \`adlb.PARAMCD = 'HGB'\`
* Apply filter: \`adlb.ANL01FL = 'Y'\`
* Apply filter: \`adlb.AVISIT = 'WEEK 8'\``;

const vitalPlan = `### Clinical Analytics Analysis Plan
#### 3. Derived Calculations
* **Vital Sign Summary**:
  Calculate using:
  \`AVG(advs.AVAL)\`
#### 4. Aggregations & Grouping
* Grouping: Group results by \`TRT01A\`.
#### 5. Filtering
* Apply filter: \`advs.PARAMCD = 'SYSBP'\``;

const savedAgePlan = `**1. Relevant Tables and Columns:**
* Table: \`adsl\`
  * Columns: \`USUBJID\`, \`TRT01A\`, \`AGE\`
**2. Join Conditions:**
* None (Single-table analysis using \`adsl\`).
**3. Derived Calculations:**
* Mean Age: \`AVG(adsl.AGE)\`
* Age Distribution / Summary Statistics (min, max, median, count): \`COUNT(adsl.USUBJID)\`, \`MIN(adsl.AGE)\`, \`MAX(adsl.AGE)\`
**4. Aggregations & Grouping:**
* Group by: \`adsl.TRT01A\` (Treatment Arm)
**5. Filtering:**
* None.`;

describe('analysis approval feedback', () => {
  it('shows an execution failure beside the approval action', () => {
    render(
      <ClinicalApprovalCard
        analysisPlan="Count distinct subjects in dm."
        onApprove={vi.fn()}
        onReject={vi.fn()}
        errorMessage="SQL validation failed; review the selected tables."
      />
    );

    expect(screen.getByRole('alert').textContent).toContain('SQL validation failed');
    expect(screen.getByRole('button', { name: /Approve & Continue/ })).toBeTruthy();
  });

  it('describes an adverse-event rate without exposing technical plan details', () => {
    render(<ClinicalApprovalCard analysisPlan={adverseEventPlan} onApprove={vi.fn()} onReject={vi.fn()} />);
    const text = screen.getByRole('region', { name: 'Review analysis plan' }).textContent || '';
    expect(text).toContain('adverse event occurrence');
    expect(text).toContain('percentage of subjects with at least one adverse event');
    expect(text).toContain('treatment group');
    expect(text).not.toMatch(/\b(?:adsl|adae|USUBJID|TRT01A|JOIN|COUNT)\b/i);
  });

  it('describes the supported laboratory calculation and Week 8 selection', () => {
    const summary = summarizeClinicalPlan(laboratoryPlan);
    expect(summary.analyze.join(' ')).toContain('hemoglobin');
    expect(summary.method.join(' ')).toContain('Week 8');
    expect(summary.method.join(' ')).toContain('treatment group');
    expect(summary.output.join(' ')).toContain('Mean change from baseline');
    expect(summary.output.join(' ')).toContain('Mean percentage change');
    expect(JSON.stringify(summary)).not.toMatch(/\b(?:adlb|PARAMCD|ANL01FL|AVG|CHG)\b/);
  });

  it('flags a requested measurement when the technical plan does not select it', () => {
    const incompleteSelection = laboratoryPlan.replace("* Apply filter: `adlb.PARAMCD = 'HGB'`\n", '');
    const summary = summarizeClinicalPlan(incompleteSelection, 'Compare mean hemoglobin change at Week 8.');
    expect(summary.limitation).toContain('does not specify a hemoglobin-only selection');
    expect(summary.analyze.join(' ')).not.toContain('Focus on hemoglobin');
  });

  it('describes a vital-sign comparison without inventing change from baseline', () => {
    const summary = summarizeClinicalPlan(vitalPlan);
    expect(summary.analyze.join(' ')).toContain('systolic blood pressure');
    expect(summary.analyze.join(' ')).toContain('treatment group');
    expect(summary.output.join(' ')).not.toContain('change from baseline');
  });

  it('explains the saved age plan and flags unsupported extra statistics', () => {
    const question = 'What is the age distribution of subjects across treatment groups, and what is the mean age in each group?';
    const summary = summarizeClinicalPlan(savedAgePlan, question);
    expect(summary.analyze.join(' ')).toContain('subject age');
    expect(summary.analyze.join(' ')).toContain('treatment group');
    expect(summary.output.join(' ')).toContain('Mean age in each treatment group');
    expect(summary.limitation).toContain('does not define age groups');
    expect(summary.limitation).toContain('median');
    expect(JSON.stringify(summary)).not.toMatch(/\b(?:adsl|USUBJID|TRT01A|AVG)\b/);
  });

  it('previews age bands and mean age from an executable plan', () => {
    const plan = `#### 3. Derived Calculations
* **Age Distribution And Mean**:
  Calculate using: \`ROUND(AVG(adsl.AGE), 2); COUNT(DISTINCT CASE WHEN adsl.AGE < 40 THEN adsl.USUBJID END); COUNT(DISTINCT CASE WHEN adsl.AGE BETWEEN 40 AND 59 THEN adsl.USUBJID END); COUNT(DISTINCT CASE WHEN adsl.AGE >= 60 THEN adsl.USUBJID END)\`
#### 4. Aggregations & Grouping
* Group results by \`TRT01A\`.
#### 5. Filtering
* Apply filter: \`adsl.AGE IS NOT NULL\``;
    const summary = summarizeClinicalPlan(plan);
    expect(summary.method.join(' ')).toContain('under 40, 40–59, and 60 or older');
    expect(summary.output.join(' ')).toContain('Mean age in each treatment group');
    expect(summary.output.join(' ')).toContain('Subject counts in each age group');
    expect(summary.limitation).toBeUndefined();
  });

  it('keeps approval and revision callbacks while displaying a revised summary', () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    const { rerender } = render(<ClinicalApprovalCard analysisPlan={adverseEventPlan} onApprove={onApprove} onReject={onReject} />);
    fireEvent.click(screen.getByRole('button', { name: /Approve & Continue/ }));
    expect(onApprove).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole('button', { name: 'Revise Plan' }));
    fireEvent.change(screen.getByPlaceholderText(/Please group the analysis/), { target: { value: 'Use Week 8' } });
    fireEvent.click(screen.getByRole('button', { name: 'Request Revised Plan' }));
    expect(onReject).toHaveBeenCalledWith('Use Week 8');
    rerender(<ClinicalApprovalCard analysisPlan={laboratoryPlan} onApprove={onApprove} onReject={onReject} planVersion={2} />);
    expect(screen.getByText('Mean change from baseline.')).toBeTruthy();
  });

  it('handles missing plan details without exposing them or inventing a calculation', () => {
    const summary = summarizeClinicalPlan('#### 1. Relevant Tables and Columns\n* adlb');
    expect(summary.limitation).toContain('incomplete');
    expect(JSON.stringify(summary)).not.toContain('adlb');
    expect(() => summarizeClinicalPlan(null)).not.toThrow();
  });
});
