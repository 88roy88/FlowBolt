{{/*
Expand the name of the chart.
*/}}
{{- define "langfuse.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this
(by the DNS naming spec).
*/}}
{{- define "langfuse.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name + version used by the chart label.
*/}}
{{- define "langfuse.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
*/}}
{{- define "langfuse.labels" -}}
helm.sh/chart: {{ include "langfuse.chart" . }}
{{ include "langfuse.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels (stable — used by Services and Deployments).
*/}}
{{- define "langfuse.selectorLabels" -}}
app.kubernetes.io/name: {{ include "langfuse.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Render a full image reference from an image object with .repository and .tag.
Usage: {{ include "langfuse.image" .Values.images.postgres }}
*/}}
{{- define "langfuse.image" -}}
{{- printf "%s:%s" .repository .tag }}
{{- end }}

{{/*
Pod security context — base (all pods).
Sets fsGroup so every PVC mount is group-writable by securityContext.fsGroup.
seccompProfile RuntimeDefault satisfies OpenShift restricted-v2 SCC.
*/}}
{{- define "langfuse.podSecurityContext" -}}
fsGroup: {{ .Values.securityContext.fsGroup }}
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Pod security context with explicit runAsUser.
Use for services that tolerate an arbitrary non-root UID
(clickhouse, minio, langfuse-web, langfuse-worker).
*/}}
{{- define "langfuse.podSecurityContextWithUser" -}}
runAsNonRoot: true
runAsUser: {{ .Values.securityContext.runAsUser }}
fsGroup: {{ .Values.securityContext.fsGroup }}
seccompProfile:
  type: RuntimeDefault
{{- end }}

{{/*
Container security context — compatible with OpenShift restricted-v2 SCC.
Drop ALL capabilities, forbid privilege escalation.
*/}}
{{- define "langfuse.containerSecurityContext" -}}
allowPrivilegeEscalation: false
capabilities:
  drop:
    - ALL
{{- end }}

{{/*
Shared name for the credentials Secret.
*/}}
{{- define "langfuse.secretName" -}}
{{- include "langfuse.fullname" . }}-credentials
{{- end }}

{{/*
Computed NEXTAUTH_URL: user-supplied value or https://<route.host>.
*/}}
{{- define "langfuse.nextauthUrl" -}}
{{- .Values.langfuse.nextauthUrl | default (printf "https://%s" .Values.route.host) }}
{{- end }}

{{/*
Shared environment variables for web and worker
*/}}
{{- define "langfuse.commonEnv" -}}
- name: DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: database-url
- name: SALT
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: salt
- name: ENCRYPTION_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: encryption-key
- name: TELEMETRY_ENABLED
  value: {{ .Values.langfuse.telemetryEnabled | quote }}
- name: LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES
  value: {{ .Values.langfuse.enableExperimentalFeatures | quote }}
- name: CLICKHOUSE_MIGRATION_URL
  value: {{ printf "clickhouse://%s-clickhouse:9000" (include "langfuse.fullname" .) | quote }}
- name: CLICKHOUSE_URL
  value: {{ printf "http://%s-clickhouse:8123" (include "langfuse.fullname" .) | quote }}
- name: CLICKHOUSE_USER
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: clickhouse-user
- name: CLICKHOUSE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: clickhouse-password
- name: CLICKHOUSE_CLUSTER_ENABLED
  value: "false"
- name: LANGFUSE_S3_EVENT_UPLOAD_BUCKET
  value: {{ .Values.minio.bucket | quote }}
- name: LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT
  value: {{ printf "http://%s-minio:9000" (include "langfuse.fullname" .) | quote }}
- name: LANGFUSE_S3_EVENT_UPLOAD_REGION
  value: "us-east-1"
- name: LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: minio-root-user
- name: LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: minio-root-password
- name: LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE
  value: "true"
- name: LANGFUSE_S3_MEDIA_UPLOAD_BUCKET
  value: {{ .Values.minio.bucket | quote }}
- name: LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT
  value: {{ printf "http://%s-minio:9000" (include "langfuse.fullname" .) | quote }}
- name: LANGFUSE_S3_MEDIA_UPLOAD_REGION
  value: "us-east-1"
- name: LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: minio-root-user
- name: LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: minio-root-password
- name: LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE
  value: "true"
- name: REDIS_HOST
  value: {{ printf "%s-redis" (include "langfuse.fullname" .) | quote }}
- name: REDIS_PORT
  value: "6379"
- name: REDIS_AUTH
  valueFrom:
    secretKeyRef:
      name: {{ include "langfuse.secretName" . }}
      key: redis-password
- name: REDIS_TLS_ENABLED
  value: "false"
{{- end }}
