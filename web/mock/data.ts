/* =====================================================
 * 模拟后端数据（从 prototype/mock-data.js 迁移）
 * 仅供 mock/plugin.ts 使用，不参与前端打包。
 * ===================================================== */

// ---------- 用户 ----------
export const USER_PROFILE = {
  id: 'amy',
  name: 'Amy',
  avatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=47',
  level: 6,
  levelTitle: '口语达人',
  totalHours: 42,
}

export const USER_STATS = {
  todayMinutes: 24,
  streakDays: 7,
}

// ---------- 看图讲故事 ----------
export interface PicStoryRow {
  title: string
  seed: string
  cat: string
  sentences: string[]
}

export const PIC_STORIES: PicStoryRow[] = [
  { title: '公园野餐', seed: 'picnic', cat: '家庭生活', sentences: ['A happy family is having a picnic in the sunny park.', 'They are sharing sandwiches and fresh fruit.', 'Everyone is laughing and having a great time.'] },
  { title: '海边拾贝', seed: 'beach', cat: '户外探索', sentences: ['The children are picking shells on the beach.', 'Waves are rolling in and out gently.', 'A little crab is hiding under a big rock.'] },
  { title: '奇妙的动物园之旅', seed: 'zoo', cat: '动物自然', sentences: ['We saw many animals at the zoo today.', 'The monkeys are jumping from tree to tree.', 'A tall giraffe is eating leaves quietly.'] },
  { title: '雪地里的小狗', seed: 'snowdog', cat: '动物自然', sentences: ['A little dog is playing in the white snow.', 'It is running after a red ball.', 'Its footprints look like small flowers.'] },
  { title: '生日派对', seed: 'birthday', cat: '节日活动', sentences: ['Today is my birthday and I am so happy.', 'My friends are singing the birthday song.', 'I made a wish and blew out the candles.'] },
  { title: '一起放风筝', seed: 'kite', cat: '户外探索', sentences: ['We are flying a colorful kite in the field.', 'The wind is strong and the kite flies high.', 'It looks like a bird dancing in the sky.'] },
  { title: '森林探险', seed: 'forest', cat: '户外探索', sentences: ['We are going on an adventure in the forest.', 'Tall trees are blocking the bright sun.', 'We heard birds singing in the branches.'] },
  { title: '快乐的农场', seed: 'farm', cat: '动物自然', sentences: ['The farm is full of happy animals.', 'Cows are eating grass in the field.', 'The farmer is collecting fresh eggs.'] },
]

// ---------- 分类 ----------
export const CATS: Record<string, string[]> = {
  storyRead: ['全部', '动物自然', '家庭生活', '户外探索', '节日活动'],
  dialogueRead: ['全部', '日常对话', '旅行出行', '健康生活'],
  listenStory: ['全部', '动物自然', '家庭生活', '户外探索', '节日活动'],
  picStory: ['全部', '动物自然', '家庭生活', '户外探索', '节日活动'],
}

// ---------- 辅助卡片示例句 ----------
export const ASSIST_HINTS: Record<string, { zh: string; en: string }> = {
  chat: { zh: '很好，我和同学一起玩了足球。', en: 'It was great. I played football with my classmates.' },
  picture: { zh: '这张图讲的是野餐的故事。', en: 'This picture is about a picnic story.' },
}

// ---------- 语音评分（保持与原型一致的随机分布） ----------
export const SCORE_RANGES: Record<string, [number, number]> = {
  assist: [70, 30],
  dialogue: [84, 12],
  story: [85, 12],
  picture: [75, 24],
}
