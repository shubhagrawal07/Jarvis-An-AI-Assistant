import { Audio } from 'expo-av';
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Modal,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { api, Task } from '../api';
import { useAuth } from '../context/AuthContext';

function localTodayIso(): string {
  const n = new Date();
  const p = (x: number) => String(x).padStart(2, '0');
  return `${n.getFullYear()}-${p(n.getMonth() + 1)}-${p(n.getDate())}`;
}

export default function TodayScreen() {
  const { logout, email, score, refresh } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [cmd, setCmd] = useState('');
  const [msg, setMsg] = useState<string | null>(null);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [eodOpen, setEodOpen] = useState(false);
  const [eodNotes, setEodNotes] = useState('');

  const load = useCallback(async () => {
    const t = await api.tasksToday();
    setTasks(t);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        await load();
      } finally {
        setLoading(false);
      }
    })();
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    try {
      await load();
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }

  async function sendTextCommand() {
    if (!cmd.trim()) return;
    setMsg(null);
    try {
      const r = await api.commandText(cmd.trim());
      setMsg(r.message);
      setCmd('');
      await load();
      await refresh();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Error');
    }
  }

  async function toggleRecord() {
    if (recording) {
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);
      if (uri) {
        try {
          const r = await api.commandVoice(uri);
          setMsg(r.message);
          await load();
          await refresh();
        } catch (e: unknown) {
          setMsg(e instanceof Error ? e.message : 'Voice failed');
        }
      }
      return;
    }
    const perm = await Audio.requestPermissionsAsync();
    if (perm.status !== 'granted') {
      setMsg('Microphone permission required');
      return;
    }
    await Audio.setAudioModeAsync({ allowsRecordingIOS: true, playsInSilentModeIOS: true });
    const rec = new Audio.Recording();
    await rec.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
    await rec.startAsync();
    setRecording(rec);
  }

  async function complete(id: string) {
    await api.completeTask(id);
    await load();
    await refresh();
  }

  async function closeDay() {
    try {
      await api.closeDay(localTodayIso(), eodNotes.trim() || undefined);
      setEodOpen(false);
      setEodNotes('');
      await load();
      await refresh();
      setMsg('Day closed. Missed tasks updated.');
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Close failed');
    }
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#3b82f6" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.hi}>Hello</Text>
          <Text style={styles.email}>{email}</Text>
        </View>
        <View style={styles.scoreBox}>
          <Text style={styles.scoreLabel}>Score</Text>
          <Text style={styles.score}>{score}</Text>
        </View>
      </View>

      <Text style={styles.section}>Today</Text>
      <FlatList
        style={{ flex: 1 }}
        data={tasks}
        keyExtractor={(item) => item.id}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        ListEmptyComponent={<Text style={styles.empty}>No tasks due today.</Text>}
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={{ flex: 1 }}>
              <Text style={styles.taskTitle}>{item.title}</Text>
              <Text style={styles.meta}>
                {item.priority.toUpperCase()} · {item.status}
              </Text>
            </View>
            {item.status === 'pending' ? (
              <Pressable style={styles.doneBtn} onPress={() => complete(item.id)}>
                <Text style={styles.doneText}>Done</Text>
              </Pressable>
            ) : null}
          </View>
        )}
      />

      <View style={styles.cmdBox}>
        <TextInput
          style={styles.cmdInput}
          placeholder="Voice or type: schedule meeting 5pm…"
          placeholderTextColor="#64748b"
          value={cmd}
          onChangeText={setCmd}
          onSubmitEditing={sendTextCommand}
        />
        <Pressable style={styles.micBtn} onPress={toggleRecord}>
          <Text style={styles.micText}>{recording ? 'Stop' : 'Rec'}</Text>
        </Pressable>
        <Pressable style={styles.sendBtn} onPress={sendTextCommand}>
          <Text style={styles.sendText}>Send</Text>
        </Pressable>
      </View>
      {msg ? <Text style={styles.feedback}>{msg}</Text> : null}

      <View style={styles.footer}>
        <Pressable style={styles.eodBtn} onPress={() => setEodOpen(true)}>
          <Text style={styles.eodText}>End of day review</Text>
        </Pressable>
        <Pressable onPress={() => logout()}>
          <Text style={styles.out}>Sign out</Text>
        </Pressable>
      </View>

      <Modal visible={eodOpen} transparent animationType="slide">
        <View style={styles.modalBg}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>Close today</Text>
            <Text style={styles.modalHint}>
              Marks remaining pending tasks for today as missed (after review). Add optional notes.
            </Text>
            <TextInput
              style={styles.notes}
              placeholder="Notes (optional)"
              placeholderTextColor="#64748b"
              value={eodNotes}
              onChangeText={setEodNotes}
              multiline
            />
            <Pressable style={styles.confirmBtn} onPress={closeDay}>
              <Text style={styles.confirmText}>Confirm close day</Text>
            </Pressable>
            <Pressable onPress={() => setEodOpen(false)}>
              <Text style={styles.cancel}>Cancel</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0f172a' },
  container: { flex: 1, backgroundColor: '#0f172a', paddingTop: 56, paddingHorizontal: 16 },
  header: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 },
  hi: { color: '#94a3b8', fontSize: 14 },
  email: { color: '#f8fafc', fontSize: 16, fontWeight: '600' },
  scoreBox: { alignItems: 'flex-end' },
  scoreLabel: { color: '#94a3b8', fontSize: 12 },
  score: { color: '#f8fafc', fontSize: 22, fontWeight: '700' },
  section: { color: '#94a3b8', fontSize: 13, marginBottom: 8, textTransform: 'uppercase' },
  empty: { color: '#64748b', paddingVertical: 24, textAlign: 'center' },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    borderRadius: 14,
    padding: 14,
    marginBottom: 10,
  },
  taskTitle: { color: '#f8fafc', fontSize: 16, fontWeight: '600' },
  meta: { color: '#94a3b8', fontSize: 13, marginTop: 4 },
  doneBtn: { backgroundColor: '#22c55e', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 10 },
  doneText: { color: '#fff', fontWeight: '600' },
  cmdBox: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 8 },
  cmdInput: {
    flex: 1,
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 12,
    color: '#f8fafc',
  },
  micBtn: { backgroundColor: '#334155', padding: 12, borderRadius: 12 },
  micText: { color: '#f8fafc', fontWeight: '600' },
  sendBtn: { backgroundColor: '#3b82f6', padding: 12, borderRadius: 12 },
  sendText: { color: '#fff', fontWeight: '600' },
  feedback: { color: '#a5b4fc', marginTop: 8, marginBottom: 8 },
  footer: { paddingVertical: 16, gap: 12 },
  eodBtn: { backgroundColor: '#4f46e5', padding: 14, borderRadius: 12, alignItems: 'center' },
  eodText: { color: '#fff', fontWeight: '600' },
  out: { color: '#94a3b8', textAlign: 'center' },
  modalBg: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    padding: 24,
  },
  modalCard: { backgroundColor: '#1e293b', borderRadius: 16, padding: 20 },
  modalTitle: { color: '#f8fafc', fontSize: 20, fontWeight: '700', marginBottom: 8 },
  modalHint: { color: '#94a3b8', fontSize: 14, marginBottom: 12 },
  notes: {
    backgroundColor: '#0f172a',
    borderRadius: 12,
    padding: 12,
    color: '#f8fafc',
    minHeight: 80,
    marginBottom: 16,
  },
  confirmBtn: { backgroundColor: '#22c55e', padding: 14, borderRadius: 12, alignItems: 'center' },
  confirmText: { color: '#fff', fontWeight: '700' },
  cancel: { color: '#94a3b8', textAlign: 'center', marginTop: 12 },
});
