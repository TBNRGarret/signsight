# Đăng nhập và phân quyền SignSight

Hệ thống có tài khoản, phiên cookie/Bearer, phân quyền API và trang quản lý, migration và giao diện web responsive. Luồng ảnh/YOLO và đóng góp dùng chung phiên đăng nhập này.

## Cài đặt và chạy

Chạy từ thư mục gốc dự án:

```powershell
python -m pip install -r backend/requirements-dev.txt
python -m backend.manage migrate
python -m backend.manage bootstrap-admin --username owner --email owner@example.com
python -m uvicorn backend.app.main:app --reload --port 8000
```

Lệnh bootstrap hỏi mật khẩu và yêu cầu nhập lại; mật khẩu dài 10–128 ký tự. Không có tài khoản/mật khẩu admin mặc định. Khi đã có admin hoạt động, bootstrap không tạo thêm admin.

Mở `http://127.0.0.1:8000/web/index.html` để đăng nhập web; Swagger ở `http://127.0.0.1:8000/docs`. Giao diện được phục vụ cùng backend và dùng API tương đối. API của điện thoại trong bước mobile cần địa chỉ LAN hoặc deployment có thể truy cập được.

## Tạo manager

1. Tạo tài khoản thông thường qua `POST /api/v1/auth/register` trong Swagger. JSON gồm `username`, `email`, `password`. Tài khoản luôn có role `user`; gửi thêm role/quyền bị từ chối.
2. Admin đăng nhập web, mở danh sách tài khoản, đổi role tài khoản đó thành `manager` và lưu.
3. Manager đăng nhập web bằng tài khoản của mình. Admin cũng có quyền quản lý biển báo.

## Các API tài khoản

| Endpoint | Quyền | Hành vi |
| --- | --- | --- |
| `POST /api/v1/auth/register` | Công khai | Tạo user; username/email không trùng, không phân biệt hoa/thường. |
| `POST /api/v1/auth/login` | Công khai | JSON username/password; trả token, hạn phiên và profile an toàn. |
| `POST /api/v1/auth/token` | Công khai | Form OAuth2 cho nút Authorize của Swagger. |
| `GET /api/v1/auth/me` | Đăng nhập | Profile hiện tại. |
| `POST /api/v1/auth/logout` | Đăng nhập | Thu hồi phiên hiện tại; các phiên khác giữ nguyên. |
| `POST /api/v1/auth/change-password` | Đăng nhập | Kiểm tra mật khẩu hiện tại; đổi mật khẩu và vô hiệu hóa mọi phiên cũ. |
| `GET /api/v1/me/contributions` | Đăng nhập | Chỉ bản ghi của chính user; offset/limit, tối đa 100 mỗi lần. |
| `GET /api/v1/admin/users` | Admin | Danh sách tài khoản có phân trang; không trả mật khẩu/hash/token. |
| `PATCH /api/v1/admin/users/{id}` | Admin | Đổi `user`/`manager` hoặc khóa/mở tài khoản; ghi audit. |

Tài khoản admin được bảo vệ khỏi sửa/xóa quyền qua PATCH này. API không cấp role admin. Tài khoản bị khóa mất quyền ngay và phiên cũ vẫn vô hiệu sau khi mở lại.

## Quyền đối với các API cũ

- Xem bản đồ và truy vấn tuyến vẫn là thao tác công khai.
- `/signs/classify` yêu cầu đăng nhập.
- `/signs/register` là đường nhập thủ công của manager/admin và được đánh dấu deprecated. Server tự gán `created_by`; client gửi trường này bị từ chối. Confidence ở API thủ công là dữ liệu nhập của người quản lý, không phải kết quả inference đã được server xác minh.
- `/revalidation/{id}`, `/revalidation/pending` và `/revalidation/duplicates` yêu cầu manager/admin. `confirmed_by` lấy từ phiên, không nhận từ payload.
- Bước tiếp theo sẽ bổ sung observations/reports cho user; user chưa được dùng API quản lý cũ để sửa trực tiếp dữ liệu đã công bố.

## Phiên và mật khẩu

- Mật khẩu được hash bằng Argon2id. Tài khoản cũ chưa có mật khẩu không được cấp mật khẩu mặc định.
- Token phiên là chuỗi ngẫu nhiên 256 bit. Database chỉ giữ SHA-256 của token, hạn phiên, user và trạng thái thu hồi.
- Quyền và trạng thái tài khoản được kiểm tra trên database mỗi request, thay đổi quyền áp dụng cho phiên đã mở.
- Credential version chặn cả phiên được tạo đồng thời với việc đổi mật khẩu/khóa tài khoản bằng credential cũ.
- Web dùng cookie `signsight_session` HttpOnly, SameSite=Lax, host hiện tại và path `/`; bật Secure khi chạy HTTPS. Đăng nhập một lần dùng chung các trang, kể cả reload/tab mới trong cùng trình duyệt. Hạn phiên mặc định 8 giờ; chọn **Ghi nhớ đăng nhập 30 ngày trên thiết bị này** để tạo phiên dài hạn. Không tự gia hạn khi chuyển trang. Mật khẩu/token không lưu trong localStorage/sessionStorage và không tin thiết bị chỉ vì cùng IP. Cách dùng cookie theo [OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
- Từ 20/10/2026, cookie dùng path `/` để server kiểm tra quyền cả khi mở trang quản lý. Login mới xóa cookie cũ ở `/api/v1`; logout xóa cả hai path và thu hồi phiên. Phiên tạo trước thay đổi vẫn dùng API đến khi hết hạn, nhưng cần đăng nhập lại một lần để mở trang quản lý bằng cookie mới.
- Guest/user không thấy link quản lý. Server kiểm tra phiên và role khi tải `management.html`, kể cả đường dẫn tương đương; thiếu quyền được đưa về bản đồ với thông báo. Trang ảnh vẫn công khai phần giới thiệu/đăng nhập, nhưng chụp/gửi đóng góp yêu cầu đăng nhập và hàng đợi duyệt chỉ dành manager/admin. API quản lý vẫn kiểm tra role riêng, không dựa vào ẩn nút.
- Browser gửi `X-SignSight-Web: 1` và `credentials: same-origin`; JSON login có header này sẽ tạo cookie. Request ghi dùng cookie cần custom header và Origin trùng backend nếu Origin có mặt; CORS không cấp quyền cookie cho origin khác. Swagger/CLI vẫn dùng Bearer như trước, không tự tạo cookie. Authorization sai không được fallback sang cookie.
- Các trang khôi phục profile bằng `/auth/me` trước khi mở chức năng. Tab đang mở đồng bộ login/logout qua storage event (chỉ lưu tín hiệu, không chứa tài khoản/credential); khi quay lại tab sẽ kiểm tra phiên với server. Request cũ không được ghi đè phiên mới; login/logout tuần tự, có Web Locks giữa các tab nếu trình duyệt hỗ trợ.
- Đăng xuất thu hồi phiên hiện tại và xóa cookie; mọi tab dùng cookie đó mất phiên. Phiên của trình duyệt/thiết bị khác giữ nguyên. Nếu mạng lỗi, giao diện xóa trạng thái đăng nhập và lưu tín hiệu ngăn tự đăng nhập lại khi chuyển trang; việc thu hồi server vẫn chưa hoàn tất. Khi web storage bị chặn, cookie vẫn khôi phục qua trang mới nhưng không bảo đảm tín hiệu đăng xuất offline được giữ lại.
- Dùng cùng hostname: `127.0.0.1`, `localhost` và IP LAN là các host khác nhau, không chia sẻ cookie/tín hiệu web storage. Điện thoại dùng phiên riêng của trình duyệt trên thiết bị đó.
- Response lỗi validation không trả lại giá trị input; response token/profile dùng `Cache-Control: no-store`.
- Register và login có giới hạn theo IP trong tiến trình. Login JSON và form chia sẻ cùng giới hạn 20 lần/phút; register 10 lần/phút. Khi chạy nhiều worker/server, cần giới hạn dùng chung ở ingress và cấu hình trusted proxy đúng.

## Migration và database cũ

Alembic có hai revision: `0001_legacy_schema` tạo hoặc nhận diện 5 bảng cũ, `0002_accounts` bổ sung mật khẩu, trạng thái tài khoản, sessions và audit. Các lần chạy lại không áp dụng lại revision đã hoàn thành.

Tài khoản cũ giữ ID và liên kết bản ghi, nhưng mặc định bị khóa và không có mật khẩu. Role không nằm trong bộ `user/manager/admin` được chuyển về `user`. Chưa có luồng khôi phục mật khẩu tài khoản cũ; tạo tài khoản mới với định danh khác để dùng demo. Việc khôi phục cần thêm quy trình xác minh chủ tài khoản.

Migration không tự gộp những username/email cũ chỉ khác hoa/thường. Nếu gặp định danh mơ hồ, migration dừng và rollback; cần xử lý dữ liệu có chủ đích trước khi chạy lại. SQLite được bật foreign keys cho kết nối mới và transaction DDL; dữ liệu tham chiếu không hợp lệ từ prototype cũ cần được rà soát riêng.

Trước khi nâng revision của SQLite đã có bảng dữ liệu, migration tự tạo snapshot nhất quán trong thư mục `backups` cạnh database bằng SQLite backup API. Database mới hoặc đã ở revision hiện tại không tạo thêm snapshot. Có thể sao lưu thủ công bằng `python -m backend.manage backup`. PostgreSQL cần quy trình backup của deployment. Không downgrade tự động vì có thể mất credential/audit. Khi deployment nhiều worker, chạy migration một lần trước rồi tắt auto-migration trong các worker.

## Cấu hình

| Biến môi trường | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `DATABASE_URL` | SQLite `backend/signsight.db` | Database của backend và management CLI. |
| `SIGNSIGHT_SESSION_MINUTES` | `480` | Thời hạn phiên 1–1.440 phút; tính cho phiên mới. |
| `SIGNSIGHT_REMEMBER_DAYS` | `30` | Phiên browser khi chọn ghi nhớ; 1–90 ngày. Giao diện mặc định ghi 30 ngày, cần đồng bộ nhãn nếu đổi cấu hình. |
| `SIGNSIGHT_AUTO_MIGRATE` | `true` | Local startup tự chạy migration. `false` yêu cầu database đã ở revision hiện tại. |
| `SIGNSIGHT_CORS_ORIGINS` | localhost/127.0.0.1 port 5173 và 8080 | Danh sách origin HTTP(S) phân cách bằng dấu phẩy. Không chấp nhận wildcard hoặc `null`. |

## Kiểm tra

### Web request và kết quả thao tác chưa rõ

Lớp request dùng chung có deadline **15 giây cho GET/HEAD**, **90 giây cho thao tác ghi**, tính cả đọc JSON/blob. Caller có thể truyền `timeoutMs` (1–90.000 ms), `signal`, và `cancelKey` cho request đọc. Request đọc cùng `cancelKey` hủy lượt trước; đổi phiên/tài khoản/vai trò hủy các lượt đọc cũ. Hủy/timeout luôn kết thúc promise và dọn timer/listener, kể cả transport không phản hồi abort. Không tự retry POST/PATCH. Abort không chứng minh server đã dừng thao tác ghi.

Error có `status`, `code` (`REQUEST_TIMEOUT`, `REQUEST_CANCELLED`, `NETWORK_ERROR` cho lỗi transport) và `outcomeUnknown`. Lỗi mạng/deadline/5xx khi ghi có thể xảy ra sau khi server đã commit. Web quản trị giữ ghi chú trong tab, khóa quyết định đối nghịch và cho bấm **Kiểm tra kết quả** để gửi lại đúng mã/nội dung. Nếu mục đã rời hàng chờ, nút **Chờ đối chiếu** phía trên các tab mở lại đúng thao tác đó. Sau 409, trang đọc đúng mục hiện tại thay vì suy đoán thành công. Kết quả đối chiếu vẫn được giữ khi chuyển qua hàng khác.

Ba API `POST /manager/observations/{id}/review`, `/manager/reports/{id}/review`, `/manager/duplicates/{id}/review` nhận `Idempotency-Key` theo cùng quy tắc upload/đóng góp. Khóa gắn với tài khoản, loại thao tác, resource và body; biên nhận commit cùng quyết định. Replay cùng ý định trả 200 và cùng resource, không lặp bằng chứng/audit/gộp biển. Client cũ không gửi khóa vẫn nhận 409 khi duyệt lại. Dùng bảng `0007_write_receipts` đã có, không thêm migration cho phần này. `GET /manager/duplicates/{id}` chỉ dành cho manager/admin để đọc trạng thái đối chiếu.

Ghi chú/ý định chờ đối chiếu chỉ nằm trong RAM của trang: reload/đóng tab hoặc đổi phiên/vai trò sẽ xóa chúng. Client không lưu cookie/token/password vào web storage. Sửa tài khoản/cấu hình có deadline và thông báo kết quả chưa rõ; chưa có replay bằng khóa cho hai loại sửa này, nên đọc lại trạng thái trước khi thử lại. Kiểm thử browser dùng database/inference giả lập và hạn mức riêng cao hơn cho workload localhost; hạn mức production vẫn được kiểm tra bằng test Python.

Migration `0007_write_receipts` thêm bảng biên nhận gửi lại; không sửa ID ảnh, nhãn hoặc đóng góp cũ. Trước khi chạy phiên bản mới trên runtime riêng, dừng server và chạy `python -m backend.manage migrate` bằng môi trường Python của dự án. Cơ chế migration hiện có tạo backup trước khi nâng schema SQLite cũ. Thay đổi này chỉ được kiểm thử trên database tạm; chưa chạy migration trên dữ liệu cá nhân.

`POST /api/v1/images` và `POST /api/v1/observations` nhận header tùy chọn `Idempotency-Key` (8–128 ký tự ASCII: chữ, số, `.`, `_`, `:`, `-`). Lưu một mã cho mỗi thao tác trước khi gửi. Gửi lại cùng mã/nội dung trả 201 với cùng resource ID; đổi nội dung trả 409. Mã được tách theo tài khoản và loại thao tác; filename không thuộc danh tính upload, nhưng byte ảnh gốc và media type có. Biên nhận và resource được commit cùng transaction, nên retry đồng thời không tạo thêm ảnh/đóng góp. Client không dùng mã vẫn giữ hành vi cũ. Biên nhận chưa tự hết hạn; không xóa tùy ý vì sẽ mất khả năng đối chiếu retry. Replay đóng góp trả trạng thái hiện tại, kể cả quyết định duyệt sau đó.

Upload dùng worker đồng bộ cho đọc file, giải mã/làm sạch ảnh và transaction database; không chạy decoder trực tiếp trên event loop. Giới hạn byte/pixel, loại ảnh và cleanup khi transaction lỗi được giữ nguyên. Đây chưa phải benchmark tải thật hoặc giới hạn hàng đợi inference.

Hai API đọc tương thích cũ `GET /api/v1/signs` và `POST /api/v1/navigation/route-signs` cũng yêu cầu phiên hợp lệ, giống API map hiện tại. User, manager và admin đều được đọc; quyền đọc không cấp quyền duyệt. Phiên hết hạn, thu hồi hoặc tài khoản bị khóa bị chặn trước khi chạy truy vấn/lifecycle. Cấu trúc phản hồi và bộ lọc cho client đã đăng nhập giữ nguyên.

API raw route-signs giới hạn 20 yêu cầu/phút/IP trong tiến trình hiện tại; vượt giới hạn trả 429 kèm `Retry-After` trước bước tính khoảng cách. Đây không phải giới hạn phân tán cho nhiều worker. Phân trang và tối ưu truy vấn của danh sách cũ vẫn là hạng mục riêng trong audit A12.

```powershell
python -m pytest tests -q
node --test tests/frontend_auth.test.cjs
python -m pytest tests/test_images_observations.py tests/test_duplicate_review.py tests/test_reports_policy.py -q
```

Test Python và integration script dùng database tạm. Test browser session kiểm tra cookie qua các trang, hết hạn, logout, Secure trên HTTPS, chặn cookie write khác origin và giữ hợp đồng Bearer. Test JavaScript kiểm tra khôi phục phiên, đồng bộ tab, logout offline, request trả muộn và khởi tạo dữ liệu khi phiên được khôi phục. Các kiểm tra này chưa thay thế nghiệm thu giao diện trên trình duyệt điện thoại.

## Tài liệu kỹ thuật

- [argon2-cffi PasswordHasher](https://argon2-cffi.readthedocs.io/en/stable/howto.html)
- [Alembic programmatic migrations](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)
- [SQLAlchemy SQLite transactions và foreign keys](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
