// Тело загрузки файла в моках. Сначала — штатный request.formData(); если файла в нём нет
// (так бывает в Safari, когда в имени файла кириллица), разбираем multipart сами.

export interface Upload {
  file: File | null;
  fields: Record<string, string>;
}

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function indexOf(haystack: Uint8Array, needle: Uint8Array, from: number): number {
  outer: for (let i = from; i <= haystack.length - needle.length; i++) {
    for (let j = 0; j < needle.length; j++) if (haystack[i + j] !== needle[j]) continue outer;
    return i;
  }
  return -1;
}

function parseMultipart(bytes: Uint8Array, boundary: string): Upload {
  const delimiter = encoder.encode(`--${boundary}`);
  const headerEnd = encoder.encode('\r\n\r\n');
  const result: Upload = { file: null, fields: {} };
  let start = indexOf(bytes, delimiter, 0);
  while (start !== -1) {
    const partStart = start + delimiter.length + 2; // после разделителя — \r\n (или -- в конце)
    const next = indexOf(bytes, delimiter, partStart);
    if (next === -1) break;
    const headersEnd = indexOf(bytes, headerEnd, partStart);
    if (headersEnd !== -1 && headersEnd < next) {
      const headers = decoder.decode(bytes.subarray(partStart, headersEnd));
      const body = bytes.subarray(headersEnd + headerEnd.length, next - 2); // без \r\n перед разделителем
      const name = /name="([^"]*)"/i.exec(headers)?.[1];
      const filename = /filename="([^"]*)"/i.exec(headers)?.[1];
      const type = /content-type:\s*([^\r\n]+)/i.exec(headers)?.[1]?.trim() ?? 'application/octet-stream';
      if (name === 'file' && filename !== undefined) result.file = new File([body.slice()], filename, { type });
      else if (name) result.fields[name] = decoder.decode(body);
    }
    start = next;
  }
  return result;
}

export async function readUpload(request: Request): Promise<Upload> {
  const raw = request.clone();
  try {
    const form = await request.formData();
    const file = form.get('file');
    if (file instanceof File) {
      const fields: Record<string, string> = {};
      form.forEach((value, key) => {
        if (typeof value === 'string') fields[key] = value;
      });
      return { file, fields };
    }
  } catch {
    // разберём сами ниже
  }
  const boundary = /boundary=(?:"([^"]+)"|([^;\s]+))/i.exec(raw.headers.get('content-type') ?? '');
  if (!boundary) return { file: null, fields: {} };
  return parseMultipart(new Uint8Array(await raw.arrayBuffer()), boundary[1] ?? boundary[2]);
}
