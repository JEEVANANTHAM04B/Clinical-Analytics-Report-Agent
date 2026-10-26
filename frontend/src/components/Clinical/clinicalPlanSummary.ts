export interface ClinicalPlanSummary {
  objective: string;
  analyze: string[];
  method: string[];
  output: string[];
  limitation?: string;
}

const dimensionLabels: Record<string, string> = {
  TRT01A: 'treatment group', ARM: 'treatment group', AVISIT: 'study visit',
  AESEV: 'adverse event severity', AEDECOD: 'adverse event type',
  PARAMCD: 'measurement type', PARAM: 'measurement type', SEX: 'sex',
  SITEID: 'study site', SITE_NAME: 'study site', ENCOUNTERCLASS: 'encounter type',
  DESCRIPTION: 'diagnosis', SAFFL: 'safety population status',
};

const metricLabels: Record<string, string> = {
  'adverse event rate by treatment': 'adverse event occurrence across treatment groups',
  'adverse event rate': 'adverse event occurrence',
  'adverse event severity distribution': 'adverse event severity',
  'serious adverse event count': 'serious adverse events',
  'adverse event count': 'adverse events',
  'top adverse events': 'the most frequently reported adverse events',
  'lab change from baseline': 'laboratory change from baseline',
  'laboratory value summary': 'laboratory measurements',
  'vital sign change from baseline': 'vital-sign change from baseline',
  'vital sign summary': 'vital-sign measurements',
  'efficacy response rate': 'clinical response rates',
  'efficacy response count': 'clinical responders',
  'enrollment by site': 'subject enrollment by study site',
  'average age': 'subject age',
  'age distribution and mean': 'subject age and its distribution',
  'sex distribution': 'subject sex distribution',
  'subjects by treatment arm': 'subject allocation across treatment groups',
  'subject disposition': 'subject completion or discontinuation',
  'total subjects': 'total enrolled subjects',
  'clinical sites count': 'participating study sites',
  'safety population': 'the safety analysis population',
};

const unique = (items: string[]) => [...new Set(items)];
const has = (text: string, pattern: RegExp) => pattern.test(text);

function identifyMetric(title: string, plan: string): string | undefined {
  if (metricLabels[title]) return metricLabels[title];
  if (/adverse event.*(?:rate|incidence)/i.test(title)) return metricLabels['adverse event rate'];
  if (/(?:lab|hemoglobin|biomarker).*(?:change|baseline)/i.test(title)) return metricLabels['lab change from baseline'];
  if (/(?:vital|blood pressure).*(?:change|baseline)/i.test(title)) return metricLabels['vital sign change from baseline'];
  if (/(?:vital|blood pressure)/i.test(title)) return metricLabels['vital sign summary'];
  if (/(?:lab|hemoglobin|biomarker)/i.test(title)) return metricLabels['laboratory value summary'];
  if (/\bage\b/i.test(title) && /AVG\s*\(\s*(?:\w+\.)?AGE\s*\)/i.test(plan)) {
    return /distribution/i.test(title + ' ' + plan)
      ? metricLabels['age distribution and mean'] : metricLabels['average age'];
  }
  if (/\bADAE\b/i.test(plan) && /COUNT\s*\(\s*DISTINCT\s+[^)]*USUBJID\s*\)\s*\/\s*COUNT/i.test(plan)) return metricLabels['adverse event rate'];
  if (/\bADLB\b/i.test(plan) && /\b(?:CHG|PCHG|BASE)\b/i.test(plan)) return metricLabels['lab change from baseline'];
  if (/\bADVS\b/i.test(plan) && /\b(?:CHG|PCHG)\b/i.test(plan)) return metricLabels['vital sign change from baseline'];
  return undefined;
}

export function summarizeClinicalPlan(plan: string | null | undefined, question = ''): ClinicalPlanSummary {
  const source = typeof plan === 'string' ? plan : '';
  const derived = source.match(/(?:####|\*\*)\s*3\.\s*Derived Calculations[^\n]*\n([\s\S]*?)(?=(?:####|\*\*)\s*4\.|$)/i)?.[1] || source;
  const metricKey = (derived.match(/\*\*([^*]+)\*\*\s*:/)?.[1] ||
    derived.match(/^\s*[*-]\s*([^:\n]+)\s*:/m)?.[1] || '').trim().toLowerCase();
  const metric = identifyMetric(metricKey, source);
  const calculation = derived.match(/Calculate using:\s*`([^`]+)`/i)?.[1] ||
    (source.match(/(?:Mean baseline|Mean change|Distinct subject count):\s*([^\n]+)/i)?.[1] || '');
  const calculationEvidence = derived || calculation;
  const grouping = source.match(/(?:####|\*\*)\s*4\.\s*Aggregations\s*(?:&|and)\s*Grouping[^\n]*\n([\s\S]*?)(?=(?:####|\*\*)\s*5\.|$)/i)?.[1] || source;
  const groupText = grouping.match(/Group results by\s*([^\n]+)/i)?.[1] ||
    grouping.match(/Group by\s*([^\n]+)/i)?.[1] || '';
  const dimensions = unique((groupText.match(/\b(?:TRT01A|ARM|AVISIT|AESEV|AEDECOD|PARAMCD|PARAM|SEX|SITEID|SITE_NAME|ENCOUNTERCLASS|DESCRIPTION|SAFFL)\b/gi) || [])
    .map((name) => dimensionLabels[name.toUpperCase()]));
  if (!dimensions.length && /treatment (?:arm|group)/i.test(groupText)) dimensions.push('treatment group');
  const filters = source.match(/(?:####|\*\*)\s*5\.\s*Filtering[^\n]*\n([\s\S]*)/i)?.[1] || source;
  const visit = (filters + ' ' + calculationEvidence).match(/\bWEEK\s+(\d+)\b/i)?.[1];
  const isPercent = has(calculationEvidence, /(?:\*\s*100|\bPCHG\b|percentage|percent)/i);
  const isDistinctSubjects = has(calculationEvidence, /COUNT\s*\(\s*DISTINCT\s+(?:\w+\.)?USUBJID/i);
  const analyze: string[] = [];
  const method: string[] = [];
  const output: string[] = [];
  const limitations: string[] = [];

  if (!metric) {
    return {
      objective: 'Review the proposed clinical analysis.',
      analyze: ['The proposed calculation cannot be described reliably from the available plan.'],
      method: ['Request a revised plan with a clear clinical objective and calculation before proceeding.'],
      output: ['The final measurements are not specified clearly enough to preview.'],
      limitation: 'The plan is incomplete or uses an unrecognized calculation. Revise it before approval.',
    };
  }

  analyze.push(`Examine ${metric}.`);
  if (dimensions.length) analyze.push(`Compare results by ${dimensions.join(' and ')}.`);
  if (visit) method.push(`Use the ${'Week ' + visit} study visit specified in the plan.`);
  if (has(filters, /TRTEMFL\s*=\s*['"]Y['"]/i)) method.push('Include treatment-emergent adverse events only.');
  if (has(filters, /AESER\s*=\s*['"]Y['"]/i)) method.push('Include serious adverse events only.');
  if (has(filters, /RESPFL\s*=\s*['"]Y['"]/i)) method.push('Include subjects marked as responders.');
  if (has(filters, /SAFFL\s*=\s*['"]Y['"]/i)) method.push('Use subjects designated for the safety analysis population.');
  if (has(filters, /ANL01FL\s*=\s*['"]Y['"]/i)) method.push('Use records designated for analysis.');
  if (has(source, /PARAMCD\s*=\s*['"]HGB['"]/i)) analyze.push('Focus on hemoglobin measurements.');
  if (has(source, /PARAMCD\s*=\s*['"]SYSBP['"]/i)) analyze.push('Focus on systolic blood pressure measurements.');
  if (/\b(?:hemoglobin|hgb)\b/i.test(question) && !has(source, /PARAMCD\s*=\s*['"]HGB['"]/i)) {
    limitations.push('The plan does not specify a hemoglobin-only selection requested in the question.');
  }
  if (/\b(?:systolic blood pressure|sysbp)\b/i.test(question) && !has(source, /PARAMCD\s*=\s*['"]SYSBP['"]/i)) {
    limitations.push('The plan does not specify a systolic blood pressure-only selection requested in the question.');
  }
  if (has(filters, /ENCOUNTERCLASS\s*=\s*['"]inpatient['"]/i)) method.push('Include inpatient encounters only.');

  const isAgeMetric = metric === metricLabels['average age'] || metric === metricLabels['age distribution and mean'];
  if (isDistinctSubjects) method.push('Count each subject only once within the relevant group.');
  if (!isAgeMetric && has(calculationEvidence, /COUNT\s*\(\s*\*/i)) method.push('Count the qualifying records.');
  if (has(calculationEvidence, /AVG\s*\(\s*(?:\w+\.)?CHG\s*\)/i)) output.push('Mean change from baseline.');
  if (has(calculationEvidence, /AVG\s*\(\s*(?:\w+\.)?PCHG\s*\)/i)) output.push('Mean percentage change from baseline.');
  if (has(calculationEvidence, /AVG\s*\(\s*(?:\w+\.)?BASE\s*\)/i)) output.push('Mean baseline value.');
  if (has(calculationEvidence, /AVG\s*\(\s*(?:\w+\.)?AVAL\s*\)/i)) output.push('Mean measured value.');
  if (has(calculationEvidence, /AVG\s*\(\s*(?:\w+\.)?AGE\s*\)/i)) {
    output.push(dimensions.includes('treatment group') ? 'Mean age in each treatment group.' : 'Mean subject age.');
  }
  if (has(calculationEvidence, /MIN\s*\(/i)) output.push('Minimum observed value.');
  if (has(calculationEvidence, /MAX\s*\(/i)) output.push('Maximum observed value.');

  if (isAgeMetric && /distribution/i.test(source + ' ' + question)) {
    if (/AGE\s*<\s*40/i.test(source) && /AGE\s+BETWEEN\s+40\s+AND\s+59/i.test(source) && /AGE\s*>=\s*60/i.test(source)) {
      method.push('Place subjects with recorded age into under 40, 40–59, and 60 or older groups.');
      output.push('Subject counts in each age group for each treatment group.');
    } else {
      limitations.push('The plan does not define age groups for the requested distribution. Revise the plan before approval.');
    }
  }
  if (isAgeMetric && /\bmedian\b/i.test(source) && !/\bmedian\b/i.test(question)) {
    limitations.push('The plan adds a median that was not requested and is not supported by the current SQL safety rules. Revise the plan before approval.');
  }

  if (metric === metricLabels['adverse event rate'] || metric === metricLabels['adverse event rate by treatment']) {
    if (isPercent && isDistinctSubjects) {
    method.push('Calculate the percentage of subjects with at least one adverse event among the subjects in each relevant group.');
    output.push('Subject counts and adverse event percentages.');
    } else limitations.push('The proposed adverse event rate calculation needs review before approval.');
  } else if (isPercent) {
    method.push('Calculate the percentage specified by the analysis plan.');
    output.push('Percentage results.');
  }
  if (metricKey.includes('change from baseline') && output.length === 0) {
    limitations.push('The plan does not specify a readable change-from-baseline calculation.');
  }
  if (!has(calculationEvidence, /\b(?:COUNT|AVG|MIN|MAX|SUM|DATEDIFF)\s*\(/i)) {
    limitations.push('The calculation is not stated clearly enough to verify from this preview.');
  }
  if (!isAgeMetric && (metricKey.includes('count') || metricKey.includes('distribution') || metricKey.includes('allocation') || metricKey.includes('enrollment'))) {
    output.push(isDistinctSubjects ? 'Distinct subject counts.' : 'Counts for the proposed clinical measure.');
  }
  if (dimensions.length) method.push(`Present the measurements separately for each ${dimensions.join(' and ')}.`);
  if (!method.length) method.push('Summarize the clinical measure described in the plan.');
  if (!output.length) output.push('A summary of the proposed clinical measure.');
  output.unshift(dimensions.length ? 'A comparison table or summary for each group.' : 'A clinical summary table.');

  const knownFilter = /\b(?:TRTEMFL|AESER|RESPFL|SAFFL|ANL01FL|PARAMCD|AVISIT|ENCOUNTERCLASS|AGE|TRT01A)\b/i;
  const filterLines = filters.split('\n').filter((line) => /(?:Apply filter|^- Filter)/i.test(line));
  if (filterLines.some((line) => !knownFilter.test(line))) limitations.push('The plan includes an additional selection rule that needs review.');
  return { objective: `Analyze ${metric}.`, analyze, method, output, limitation: limitations.join(' ') || undefined };
}
